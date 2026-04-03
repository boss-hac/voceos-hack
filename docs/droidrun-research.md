# Droidrun 調査レポート

## 概要
droidrunはAndroidデバイスをLLMエージェントで自律制御するPythonフレームワーク。
LlamaIndexのWorkflowシステム上に構築、イベント駆動の非同期アーキテクチャ。

フォーク先: https://github.com/yuyu1815/droidrun
ローカル: `/Users/yusei.iwase.01/Desktop/hack/voceos-droidrun`

---

## アーキテクチャ

### 2つの動作モード

**FastAgentモード (`reasoning=False`, デフォルト)**
```
ゴール → スクリーンショット取得 → UI状態取得 → LLM呼び出し
→ XMLツールコール解析 → ツール実行 → 結果フィードバック → ループ
→ complete() で終了
```

**推論モード (`reasoning=True`)**
```
ManagerAgent (計画) → サブゴール作成
→ ExecutorAgent (実行) → アクション実行 → Manager にフィードバック → ループ
```

### デバイス接続
- **Portal APK** (`com.droidrun.portal`) をAndroid端末にインストール
- AccessibilityService としてUIツリー情報取得
- `async_adbutils` 経由でADB接続
- `auto_setup=True` で自動インストール・有効化

---

## Python API

### 最小構成
```python
import asyncio
from droidrun import DroidAgent
from droidrun.config_manager import DroidConfig

async def main():
    config = DroidConfig()
    agent = DroidAgent(
        goal="設定アプリを開いてバッテリー残量を確認して",
        config=config,
    )
    result = await agent.run()
    print(f"成功: {result.success}, 理由: {result.reason}")

asyncio.run(main())
```

### カスタムLLM指定
```python
from llama_index.llms.anthropic import Anthropic

llms = {
    "fast_agent": Anthropic(model="claude-sonnet-4-5-latest", temperature=0.2),
}
agent = DroidAgent(goal="タスク", llms=llms, config=config)
```

### 対応LLMプロバイダ
- **Anthropic** (Claude)
- **OpenAI** (GPT-4o等)
- **GoogleGenAI** (Gemini) — デフォルト
- **Ollama** (ローカル)
- **DeepSeek**
- **OpenAILike** (互換エンドポイント)

### APIキー設定
- 環境変数: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`
- 設定ファイル: `~/.config/droidrun/.env`

---

## エージェントが使えるツール

| ツール | 機能 |
|---|---|
| `click` | UI要素インデックス指定でタップ |
| `click_at` | 座標指定でタップ |
| `long_press` | 長押し |
| `type` | テキスト入力 |
| `swipe` | スワイプ/スクロール |
| `system_button` | back/home/enter |
| `open_app` | アプリ名指定で起動 |
| `wait` | 待機 |
| `remember` | 情報を記憶 |
| `complete` | タスク完了宣言 |

### カスタムツール追加
```python
def my_tool(query: str, ctx) -> str:
    return f"結果: {query}"

custom_tools = {
    "my_tool": {
        "parameters": {"query": {"type": "string", "required": True}},
        "description": "カスタム検索ツール",
        "function": my_tool
    }
}
agent = DroidAgent(goal="...", config=config, custom_tools=custom_tools)
```

---

## MCP統合 (既に内蔵)

droidrunは **MCPクライアント** を内蔵しており、外部MCPサーバーのツールを取り込める。

```yaml
# config.yaml
mcp:
  enabled: true
  servers:
    voiceos:
      command: "python"
      args: ["-m", "voceos_mcp_server"]
      prefix: "voiceos_"
      enabled: true
```

---

## イベントストリーミング

```python
handler = agent.run()
async for event in handler.stream_events():
    if isinstance(event, ToolExecutionEvent):
        print(f"ツール: {event.tool_name} → {event.summary}")
    elif isinstance(event, FastAgentResponseEvent):
        print(f"思考: {event.thought}")
```

---

## 構造化出力

```python
from pydantic import BaseModel

class BatteryInfo(BaseModel):
    level: int
    is_charging: bool

agent = DroidAgent(goal="バッテリー確認", config=config, output_model=BatteryInfo)
result = await agent.run()
info = result.structured_output  # BatteryInfo
```

---

## 実行中のメッセージ注入
```python
agent.send_user_message("代わりにFirefoxを開いて")
```

---

## 主要設定 (DroidConfig)

| パラメータ | デフォルト | 説明 |
|---|---|---|
| `agent.max_steps` | 15 | 最大ステップ数 |
| `agent.reasoning` | False | Manager/Executorモード |
| `fast_agent.vision` | False | スクショをLLMに送る |
| `fast_agent.parallel_tools` | True | 複数ツール同時実行 |
| `device.serial` | None (自動) | デバイスシリアル |
| `device.auto_setup` | True | Portal自動セットアップ |

---

## VoiceOS連携の構想

```
音声 → VoiceOS → MCP Server (stdio)
                      ↓
              DroidAgent.run(goal=音声コマンド)
                      ↓
              Android端末操作 (Portal APK + ADB)
                      ↓
              結果をVoiceOSに返す → 音声で応答
```

### MCPサーバー側の実装イメージ
```python
from mcp.server.fastmcp import FastMCP
from droidrun import DroidAgent
from droidrun.config_manager import DroidConfig

mcp = FastMCP("android-agent")

@mcp.tool()
async def control_android(task: str) -> str:
    """音声コマンドに基づいてAndroid端末を操作する"""
    config = DroidConfig()
    agent = DroidAgent(goal=task, config=config)
    result = await agent.run()
    return f"{'成功' if result.success else '失敗'}: {result.reason}"

mcp.run(transport="stdio")
```

---

## 重要ファイルパス

| ファイル | 役割 |
|---|---|
| `droidrun/agent/droid/droid_agent.py` | メインエージェント |
| `droidrun/agent/fast_agent/fast_agent.py` | ReActループ実装 |
| `droidrun/agent/tool_registry.py` | ツール登録・実行 |
| `droidrun/mcp/adapter.py` | MCPツール変換 |
| `droidrun/mcp/client.py` | MCPクライアント |
| `droidrun/tools/driver/android.py` | Androidドライバー |
| `droidrun/portal.py` | Portal APK管理 |
| `droidrun/config_manager/config_manager.py` | 設定スキーマ |
| `droidrun/agent/utils/llm_picker.py` | LLM動的ロード |
| `droidrun/config_example.yaml` | 設定リファレンス |
