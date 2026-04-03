# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

**Nakura** — 寝る前のひらめきを翌朝の自分に届けるVoiceOS用MCPサーバー。

脳科学的知見に基づく課題解決：入眠時（N1段階）は創造性が最も高まるが記憶定着が最も弱い瞬間。音声キャプチャ→翌朝デリバリーの一気通貫体験を提供する。

### 動作フロー

```
【夜】VoiceOSセッション開始
    → MCP Resource (nakura://context) をVoiceOSが自動読み込み
    → エージェントが「今夜のひらめきをメモしませんか？」と提案
    → ユーザーが話す → record_idea ツールで ~/.nakura/YYYY-MM-DD_night.md に追記

【朝】VoiceOSセッション開始
    → MCP Resource (nakura://context) をVoiceOSが自動読み込み
    → 昨夜のメモ内容がコンテキストに注入済み
    → エージェントが内容を読み上げ・整理
```

launchd・システムプロンプト設定・ユーザーへの手動操作指示は不要。

## Tech Stack

- **Language**: Python 3.11+
- **MCP Framework**: FastMCP (`mcp` パッケージ)
- **Package Manager**: uv
- **Storage**: Markdownファイル（`~/.nakura/`、SQLite不使用）
- **Transport**: stdio

## セットアップ

```bash
cd nakura
mise trust
mise install
mise exec -- uv sync
```

## 開発コマンド

```bash
# MCPインスペクターでリソース・ツール動作確認
npx @modelcontextprotocol/inspector mise exec -- uv run python server.py

# テスト
mise exec -- uv run pytest tests/ -v
mise exec -- uv run pytest tests/test_server.py::test_record_idea -v
```

## VoiceOS連携

**Launch command:**
```
mise exec -- uv run python /path/to/nakura/server.py
```

VoiceOSがMCP Resourcesをセッション開始時に自動読み込みするため、追加設定不要。

## アーキテクチャ

```
nakura/
├── server.py       # MCPサーバー（Resource + Tool定義）
├── pyproject.toml  # uv プロジェクト設定
└── tests/
    └── test_server.py
```

### ストレージ

```
~/.nakura/
├── 2026-04-02_night.md   # 昨夜のメモ
└── 2026-04-03_night.md   # 今夜のメモ
```

ファイル形式：
```markdown
# 2026-04-03 夜のメモ

## 22:14
アプリのオンボーディングをもっとシンプルにしたい。最初の画面は1枚だけでいい。

## 22:31
ユーザーインタビューを来週やりたい。5人くらい。
```

### MCP Resource

| URI | 説明 |
|---|---|
| `nakura://context` | 時刻・ファイル状態を見て動的にコンテキストを返す |

**返却ロジック：**
```
朝（6〜10時） + 昨夜のメモあり → 昨夜のメモ内容をそのまま返す
夜（21〜24時）                  → 夜のメモ促進メッセージを返す
それ以外                         → 空文字を返す
```

### MCPツール

| ツール名 | 説明 |
|---|---|
| `record_idea` | テキストを受け取り今夜の Markdown に timestamp 付きで追記 |
| `get_last_night_memo` | 昨夜のメモを返す（手動アクセス用） |
