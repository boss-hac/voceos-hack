# VoiceOS MCP Integration Project

## Overview
VoiceOS用のカスタムMCP (Model Context Protocol) サーバーを開発するプロジェクト。
音声コマンドからツールを呼び出し、macOS上のアプリケーション操作を自動化する。

## Tech Stack
- **Language**: Python (FastMCP) or TypeScript
- **Python deps**: `mcp` (pip install mcp)
- **TypeScript deps**: `@modelcontextprotocol/sdk`, `zod`
- **Transport**: stdio (標準入出力ベース通信)
- **Platform**: macOS

## Architecture
1. MCP Serverを作成し、ツール(関数)を登録する
2. VoiceOSがstdio経由でサーバーと通信し、音声コマンドに応じてツールを呼び出す
3. ツールはAppleScript/Shortcuts等を通じてmacOSアプリを操作可能

### Python パターン
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("server-name")

@mcp.tool()
def my_tool(param: str) -> str:
    """Tool description."""
    return result

mcp.run(transport="stdio")
```

### TypeScript パターン
```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({ name: "server-name", version: "1.0.0" });

server.tool("name", "description", { param: z.string() }, async ({ param }) => {
  return { content: [{ type: "text", text: "result" }] };
});

const transport = new StdioServerTransport();
await server.connect(transport);
```

## VoiceOS連携手順
1. VoiceOS Settings -> Integrations -> Custom Integrations
2. 新しいIntegrationを追加
3. Launch commandを設定:
   - Python: `python3 /path/to/my_mcp_server.py`
   - TypeScript: `npx tsx /path/to/my-mcp-server.ts`

## Development Guidelines
- ツール関数には明確なdocstringを記述する(VoiceOSがツール選択に利用)
- パラメータには型ヒント(Python)またはZodスキーマ(TypeScript)を必ず付ける
- ツールは文字列を返す(Python)またはcontent配列を返す(TypeScript)
- macOS操作にはAppleScript (`osascript`) やApple Shortcutsを活用

## Reference
- Guide: https://www.voiceos.com/guide/build-mcp-integration
- MCP SDK (Python): https://github.com/modelcontextprotocol/python-sdk
- MCP SDK (TypeScript): https://github.com/modelcontextprotocol/typescript-sdk
