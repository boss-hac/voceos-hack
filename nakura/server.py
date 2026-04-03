from mcp.server.fastmcp import FastMCP
from datetime import datetime, date, timedelta
from pathlib import Path

STORAGE_DIR = Path.home() / ".nakura"
mcp = FastMCP("nakura")


def _get_night_file(target_date: date) -> Path:
    return STORAGE_DIR / f"{target_date}_night.md"


def _read_last_night_memo() -> str | None:
    yesterday = date.today() - timedelta(days=1)
    path = _get_night_file(yesterday)
    return path.read_text(encoding="utf-8") if path.exists() else None


@mcp.resource("nakura://context")
def get_context() -> str:
    """時刻・ファイル状態を見て動的にコンテキストを返す。VoiceOSがセッション開始時に自動読み込みする。"""
    hour = datetime.now().hour
    if 6 <= hour < 10:
        memo = _read_last_night_memo()
        if memo:
            return memo
    elif 21 <= hour <= 23:
        return "今夜のひらめきをメモしませんか？record_ideaツールでキャプチャできます。"
    return ""


@mcp.tool()
def record_idea(content: str) -> str:
    """今夜のひらめきやアイデアをMarkdownファイルに記録する。"""
    STORAGE_DIR.mkdir(exist_ok=True)
    path = _get_night_file(date.today())
    timestamp = datetime.now().strftime("%H:%M")
    if not path.exists():
        path.write_text(f"# {date.today()} 夜のメモ\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"## {timestamp}\n{content}\n\n")
    return f"メモしました（{timestamp}）"


@mcp.tool()
def get_morning_brief() -> str:
    """昨夜のメモを取得する（手動アクセス用）。"""
    memo = _read_last_night_memo()
    return memo if memo else "昨夜のメモはありません。"


if __name__ == "__main__":
    mcp.run(transport="stdio")
