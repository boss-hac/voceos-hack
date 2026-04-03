import base64
import subprocess
import time
from io import BytesIO

import pyautogui
from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent

# 誤操作防止: フェイルセーフ有効（画面端にカーソル移動でストップ）
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

mcp = FastMCP("macos-control")


VIRTUAL_SIZE = 1000


def to_screen(x: int, y: int) -> tuple[int, int]:
    """Convert virtual 1000x1000 coordinates to actual screen coordinates."""
    sw, sh = pyautogui.size()
    return int(x * sw / VIRTUAL_SIZE), int(y * sh / VIRTUAL_SIZE)


def osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 and result.stderr:
        return f"Error: {result.stderr.strip()}"
    return result.stdout.strip() or "Done"


def screenshot_result(message: str, delay: float = 0.5) -> list:
    """Return text message + screenshot as MCP content list."""
    time.sleep(delay)
    img = pyautogui.screenshot()
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return [
        TextContent(type="text", text=message),
        ImageContent(type="image", data=b64, mimeType="image/png"),
    ]


# ──────────────────────────────────────────
# A: アプリ操作
# ──────────────────────────────────────────

@mcp.tool()
def open_app(app_name: str) -> list:
    """Open an application by name (e.g. 'Safari', 'Finder', 'Slack')."""
    result = subprocess.run(["open", "-a", app_name], capture_output=True, text=True)
    if result.returncode != 0:
        return screenshot_result(f"Error: {result.stderr.strip()}", delay=0)
    return screenshot_result(f"Opened {app_name}", delay=1.0)


@mcp.tool()
def quit_app(app_name: str) -> list:
    """Quit an application by name."""
    msg = osascript(f'tell application "{app_name}" to quit')
    return screenshot_result(msg)


@mcp.tool()
def switch_to_app(app_name: str) -> list:
    """Bring an application to the foreground."""
    msg = osascript(f'tell application "{app_name}" to activate')
    return screenshot_result(msg, delay=0.5)


@mcp.tool()
def list_running_apps() -> list:
    """List all currently running applications."""
    script = (
        'tell application "System Events" to '
        'get name of every application process whose background only is false'
    )
    msg = osascript(script)
    return screenshot_result(msg, delay=0)


@mcp.tool()
def maximize_window(app_name: str) -> list:
    """Maximize (zoom) the frontmost window of the specified application."""
    script = f'''
tell application "System Events"
    tell process "{app_name}"
        set frontmost to true
        tell window 1
            set value of attribute "AXFullScreen" to true
        end tell
    end tell
end tell
'''
    msg = osascript(script)
    return screenshot_result(msg, delay=0.5)


@mcp.tool()
def resize_window(app_name: str, width: int, height: int) -> list:
    """Resize the frontmost window of the specified application."""
    script = f'''
tell application "System Events"
    tell process "{app_name}"
        set frontmost to true
        set size of window 1 to {{{width}, {height}}}
    end tell
end tell
'''
    msg = osascript(script)
    return screenshot_result(msg, delay=0.5)


@mcp.tool()
def move_window(app_name: str, x: int, y: int) -> list:
    """Move the frontmost window of the specified application to (x, y)."""
    script = f'''
tell application "System Events"
    tell process "{app_name}"
        set frontmost to true
        set position of window 1 to {{{x}, {y}}}
    end tell
end tell
'''
    msg = osascript(script)
    return screenshot_result(msg, delay=0.5)


@mcp.tool()
def open_finder_folder(path: str) -> list:
    """Open a folder in Finder (e.g. '/Users/example/Desktop')."""
    result = subprocess.run(["open", path], capture_output=True, text=True)
    if result.returncode != 0:
        return screenshot_result(f"Error: {result.stderr.strip()}", delay=0)
    return screenshot_result(f"Opened {path} in Finder", delay=1.0)


# ──────────────────────────────────────────
# C: キーボード・マウス自動操作
# ──────────────────────────────────────────

@mcp.tool()
def type_text(text: str) -> list:
    """Type the given text into the currently focused input field."""
    escaped = text.replace('"', '\\"')
    script = f'''
tell application "System Events"
    keystroke "{escaped}"
end tell
'''
    msg = osascript(script)
    return screenshot_result(msg, delay=0.3)


@mcp.tool()
def send_keystroke(key: str, modifiers: str = "") -> list:
    """Send a keyboard shortcut.

    Args:
        key: The key to press (e.g. 'c', 'v', 'return', 'tab', 'escape').
        modifiers: Comma-separated modifiers: 'command', 'shift', 'option', 'control'.
                   Example: 'command,shift' to press Cmd+Shift+<key>.
    """
    if modifiers.strip():
        mod_list = [m.strip() + " down" for m in modifiers.split(",") if m.strip()]
        mod_str = "{" + ", ".join(mod_list) + "}"
        script = f'tell application "System Events" to keystroke "{key}" using {mod_str}'
    else:
        script = f'tell application "System Events" to keystroke "{key}"'
    msg = osascript(script)
    return screenshot_result(msg, delay=0.3)


@mcp.tool()
def press_key(key_code: str) -> list:
    """Press a special key by name.

    Supported keys: return, tab, space, delete, escape, up, down, left, right,
    home, end, pageup, pagedown, f1-f12.
    """
    key_codes = {
        "return": 36, "tab": 48, "space": 49, "delete": 51, "escape": 53,
        "left": 123, "right": 124, "down": 125, "up": 126,
        "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
        "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96,
        "f6": 97, "f7": 98, "f8": 100, "f9": 101, "f10": 109,
        "f11": 103, "f12": 111,
    }
    code = key_codes.get(key_code.lower())
    if code is None:
        return screenshot_result(f"Unknown key: {key_code}", delay=0)
    msg = osascript(f'tell application "System Events" to key code {code}')
    return screenshot_result(msg, delay=0.3)


@mcp.tool()
def copy_to_clipboard(text: str) -> list:
    """Copy the given text to the system clipboard."""
    result = subprocess.run(["pbcopy"], input=text, capture_output=True, text=True)
    if result.returncode != 0:
        return screenshot_result(f"Error: {result.stderr.strip()}", delay=0)
    return screenshot_result("Copied to clipboard", delay=0)


@mcp.tool()
def get_clipboard() -> list:
    """Get the current content of the system clipboard."""
    result = subprocess.run(["pbpaste"], capture_output=True, text=True)
    msg = result.stdout or "(empty)"
    return screenshot_result(msg, delay=0)


# ──────────────────────────────────────────
# マウス操作
# ──────────────────────────────────────────

@mcp.tool()
def get_mouse_position() -> list:
    """Get the current mouse cursor position as virtual 1000x1000 coordinates."""
    ax, ay = pyautogui.position()
    sw, sh = pyautogui.size()
    vx = int(ax * VIRTUAL_SIZE / sw)
    vy = int(ay * VIRTUAL_SIZE / sh)
    return screenshot_result(f"virtual=({vx}, {vy})  actual=({ax}, {ay})", delay=0)


@mcp.tool()
def mouse_move(x: int, y: int, duration: float = 0.3) -> list:
    """Move the mouse cursor to (x, y) in virtual 1000x1000 coordinates.

    Args:
        x: Horizontal position (0-1000).
        y: Vertical position (0-1000).
        duration: Time in seconds for the movement (default 0.3).
    """
    sx, sy = to_screen(x, y)
    pyautogui.moveTo(sx, sy, duration=duration)
    return screenshot_result(f"Moved to virtual=({x}, {y})", delay=0.2)


@mcp.tool()
def mouse_click(x: int, y: int, button: str = "left") -> list:
    """Click at the given position in virtual 1000x1000 coordinates.

    Args:
        x: Horizontal position (0-1000).
        y: Vertical position (0-1000).
        button: 'left', 'right', or 'double' (default 'left').
    """
    sx, sy = to_screen(x, y)
    if button == "double":
        pyautogui.doubleClick(sx, sy)
    elif button == "right":
        pyautogui.rightClick(sx, sy)
    else:
        pyautogui.click(sx, sy)
    return screenshot_result(f"{button} click at virtual=({x}, {y})", delay=0.3)


@mcp.tool()
def mouse_drag(from_x: int, from_y: int, to_x: int, to_y: int, duration: float = 0.5) -> list:
    """Drag from one position to another in virtual 1000x1000 coordinates.

    Args:
        from_x: Start horizontal position (0-1000).
        from_y: Start vertical position (0-1000).
        to_x: End horizontal position (0-1000).
        to_y: End vertical position (0-1000).
        duration: Time in seconds for the drag (default 0.5).
    """
    sfx, sfy = to_screen(from_x, from_y)
    stx, sty = to_screen(to_x, to_y)
    pyautogui.moveTo(sfx, sfy, duration=0.2)
    pyautogui.dragTo(stx, sty, duration=duration, button="left")
    return screenshot_result(f"Dragged from virtual=({from_x}, {from_y}) to ({to_x}, {to_y})", delay=0.3)


@mcp.tool()
def mouse_scroll(amount: int, x: int = None, y: int = None) -> list:
    """Scroll up or down at the current or specified position.

    Args:
        amount: Positive to scroll up, negative to scroll down.
        x: Optional horizontal position to scroll at.
        y: Optional vertical position to scroll at.
    """
    if x is not None and y is not None:
        sx, sy = to_screen(x, y)
        pyautogui.moveTo(sx, sy, duration=0.2)
    pyautogui.scroll(amount)
    direction = "up" if amount > 0 else "down"
    return screenshot_result(f"Scrolled {direction} by {abs(amount)}", delay=0.3)


@mcp.tool()
def get_screen_size() -> list:
    """Get the screen resolution (width x height)."""
    w, h = pyautogui.size()
    return screenshot_result(f"width={w}, height={h}", delay=0)


if __name__ == "__main__":
    mcp.run(transport="stdio")
