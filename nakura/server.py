from mcp.server.fastmcp import FastMCP
from datetime import datetime, date, timedelta
from pathlib import Path

STORAGE_DIR = Path.home() / ".nakura"
mcp = FastMCP("nakura")


def _parse_now(now: str | None) -> datetime:
    """now が None なら現在時刻、文字列なら ISO 形式でパースする。"""
    return datetime.fromisoformat(now) if now else datetime.now()


def _get_night_file(target_date: date) -> Path:
    return STORAGE_DIR / f"{target_date}_night.md"


def _read_last_night_memo(today: date) -> str | None:
    yesterday = today - timedelta(days=1)
    path = _get_night_file(yesterday)
    return path.read_text(encoding="utf-8") if path.exists() else None


@mcp.resource("nakura://context")
def get_context() -> str:
    """時刻・ファイル状態を見て動的にコンテキストを返す。VoiceOSがセッション開始時に自動読み込みする。"""
    now = datetime.now()
    hour = now.hour
    if 6 <= hour < 10:
        memo = _read_last_night_memo(now.date())
        if memo:
            return memo
    elif 21 <= hour <= 23:
        return "今夜のひらめきをメモしませんか？record_ideaツールでキャプチャできます。"
    return ""


@mcp.tool()
def record_idea(content: str, now: str | None = None) -> str:
    """今夜のひらめきやアイデアをMarkdownファイルに記録する。now は ISO 形式の日時文字列（例: 2026-04-03T22:00:00）。省略時は現在時刻。"""
    dt = _parse_now(now)
    STORAGE_DIR.mkdir(exist_ok=True)
    path = _get_night_file(dt.date())
    timestamp = dt.strftime("%H:%M")
    if not path.exists():
        path.write_text(f"# {dt.date()} 夜のメモ\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"## {timestamp}\n{content}\n\n")
    return f"メモしました（{timestamp}）"


@mcp.tool()
def get_last_night_memo(now: str | None = None) -> str:
    """昨夜のメモを取得する。now は ISO 形式の日時文字列（例: 2026-04-03T07:00:00）。省略時は現在時刻を基準に昨夜のメモを返す。"""
    dt = _parse_now(now)
    memo = _read_last_night_memo(dt.date())
    return memo if memo else "昨夜のメモはありません。"


if __name__ == "__main__":
    mcp.run(transport="stdio")
