# Android操作のための技術調査まとめ

## 概要
VoiceOS MCPサーバーからmacOS経由でAndroidデバイスを操作するための技術情報。

---

## 1. ADB (Android Debug Bridge) — 基盤

### セットアップ
```bash
brew install android-platform-tools
adb version
```

### デバイス接続
- **USB**: Developer Options > USB Debugging を有効化 → USB接続 → `adb devices`
- **Wi-Fi (Android 11+)**: Developer Options > Wireless Debugging → `adb pair <IP>:<PORT> <CODE>` → `adb connect <IP>:<PORT>`
- **Wi-Fi (Android 10以下)**: USB接続 → `adb tcpip 5555` → USB外す → `adb connect <IP>:5555`

### 主要コマンド

| カテゴリ | コマンド | 説明 |
|---|---|---|
| **アプリ起動** | `adb shell am start -n <pkg>/<activity>` | Activity指定で起動 |
| **アプリ起動 (簡易)** | `adb shell monkey -p <pkg> -c android.intent.category.LAUNCHER 1` | パッケージ名のみで起動 |
| **アプリ終了** | `adb shell am force-stop <pkg>` | 強制停止 |
| **タップ** | `adb shell input tap <x> <y>` | 座標をタップ |
| **スワイプ** | `adb shell input swipe <x1> <y1> <x2> <y2> [ms]` | スワイプ |
| **長押し** | `adb shell input swipe <x> <y> <x> <y> 1000` | 同座標スワイプで代用 |
| **テキスト入力** | `adb shell input text '<string>'` | 文字列入力 |
| **キーイベント** | `adb shell input keyevent <code>` | キー送信 |
| **スクリーンショット** | `adb shell screencap /sdcard/ss.png` | 画面キャプチャ |
| **画面録画** | `adb shell screenrecord /sdcard/rec.mp4` | 最大180秒 |
| **ファイル送信** | `adb push <local> <device>` | PC→端末 |
| **ファイル取得** | `adb pull <device> <local>` | 端末→PC |
| **音量UP/DOWN** | `adb shell input keyevent 24` / `25` | 音量操作 |
| **明るさ設定** | `adb shell settings put system screen_brightness <0-255>` | 輝度変更 |
| **通知バー展開** | `adb shell cmd statusbar expand-notifications` | 通知表示 |
| **現在のアプリ取得** | `adb shell dumpsys activity activities \| grep mResumedActivity` | フォアグラウンドアプリ |

### キーイベントコード

| 操作 | コード |
|---|---|
| Home | `3` / `KEYCODE_HOME` |
| Back | `4` / `KEYCODE_BACK` |
| Recent Apps | `187` / `KEYCODE_APP_SWITCH` |
| Power | `26` / `KEYCODE_POWER` |
| Enter | `66` / `KEYCODE_ENTER` |
| Delete | `67` / `KEYCODE_DEL` |

### Intent (アプリ間連携)
```bash
# URL開く
adb shell am start -a android.intent.action.VIEW -d "https://example.com"
# 地図開く
adb shell am start -a android.intent.action.VIEW -d "geo:35.6762,139.6503"
# テキスト共有
adb shell am start -a android.intent.action.SEND --es android.intent.extra.TEXT "hello" -t "text/plain"
# ブロードキャスト送信
adb shell am broadcast -a com.myapp.ACTION --es key "value"
```

---

## 2. Python ライブラリ比較

### 推奨構成

| ライブラリ | 用途 | インストール |
|---|---|---|
| **adbutils** | ADB操作全般(基盤) | `pip install adbutils` |
| **uiautomator2** | UI要素の認識・操作 | `pip install uiautomator2` |
| **py-scrcpy-client** | リアルタイム画面取得 | `pip install scrcpy-client` |

### adbutils
ADBプロトコルをPure Pythonで実装。subprocessの代替として最適。
```python
import adbutils
d = adbutils.adb.device()
d.screenshot().save("ss.png")  # PIL Image
d.click(500, 500)
d.swipe(100, 500, 900, 500)
d.shell("input text hello")
d.app_current()
d.list_packages()
```

### uiautomator2 (最推奨)
UI要素をテキスト・ID・クラス名で検索でき、座標に依存しない操作が可能。
```python
import uiautomator2 as u2
d = u2.connect('DEVICE_SERIAL')

# UI要素操作
d(text="Settings").click()
d(resourceId="com.app:id/input").set_text("hello")
d(className="android.widget.Button").exists(timeout=5)

# ジェスチャー
d.click(x, y)
d.swipe(sx, sy, ex, ey, duration=0.5)
d.long_click(x, y)

# スクリーンショット
img = d.screenshot()  # PIL Image

# キー操作
d.press("home")
d.press("back")

# アプリ管理
d.app_start("com.package.name")
d.app_stop("com.package.name")

# UI階層取得 (XML)
xml = d.dump_hierarchy()

# シェルコマンド
d.shell("ls /sdcard")
```

### py-scrcpy-client
リアルタイムの画面フレームが必要な場合に使用。
```python
import scrcpy
client = scrcpy.Client(device="SERIAL")
client.start(threaded=True)
frame = client.last_frame  # numpy BGR array
client.control.touch(x, y, scrcpy.ACTION_DOWN)
client.control.touch(x, y, scrcpy.ACTION_UP)
```

---

## 3. 高度なツール

### scrcpy (画面ミラーリング)
```bash
brew install scrcpy
scrcpy                          # 基本ミラーリング
scrcpy --record file.mp4        # 録画
scrcpy --turn-screen-off        # 端末画面オフでミラー
```
- 低遅延 (35-70ms)、高fps (30-60)
- root不要、アプリインストール不要

### Appium (モバイル自動化フレームワーク)
- セットアップが重い (Node.js + Java + Android SDK必要)
- WebDriverプロトコルでHTTPオーバーヘッドあり
- クロスプラットフォーム対応 (iOS/Android)
- **今回のユースケースにはオーバーキル**

### Droidrun (AI駆動型自動化)
- Accessibilityサービス + CV でLLM駆動の自動化
- `pip install droidrun`
- AI agent的な自動化が必要な場合に有用

---

## 4. 推奨アーキテクチャ

```
VoiceOS → (stdio) → MCP Server (Python)
                         ├── uiautomator2  ... UI要素の認識・操作
                         ├── adbutils      ... デバイス管理・ファイル転送・シェル
                         ├── ADB intents   ... アプリ起動・URL開く・共有
                         └── scrcpy        ... リアルタイム画面取得 (必要時)
```

### なぜ uiautomator2 が最推奨か
1. **セットアップが簡単**: `pip install` のみ
2. **UI要素を意味的に操作可能**: テキスト・ID指定でタップ (座標不要)
3. **高速**: Appiumより軽量 (WebDriverレイヤーなし)
4. **十分なAPI**: スクショ・ジェスチャー・アプリ管理・シェル全て対応
5. **adbutils と同じ openatx エコシステム**: 相性が良い

---

## 5. 必要な前提条件
- Android端末で **USBデバッグ** を有効化
- macOSに `android-platform-tools` をインストール
- Python 3.10+
- `pip install mcp uiautomator2 adbutils`
