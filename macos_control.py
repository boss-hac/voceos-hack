import base64
import subprocess
import time
from io import BytesIO

import pyautogui
from PIL import ImageDraw, ImageFont
from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent

# element ID -> (x, y, w, h) in logical screen coords
_element_cache: dict[str, tuple[int, int, int, int]] = {}

# 誤操作防止: フェイルセーフ有効（画面端にカーソル移動でストップ）
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

mcp = FastMCP("computer use")

VIRTUAL_SIZE = 1000


def osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 and result.stderr:
        return f"Error: {result.stderr.strip()}"
    return result.stdout.strip() or "Done"


def get_window_bounds(app_name: str) -> tuple[int, int, int, int] | None:
    """Return (x, y, width, height) of the app's frontmost window, or None on failure."""
    script = f'''
tell application "System Events"
    tell process "{app_name}"
        set pos to position of window 1
        set sz to size of window 1
        return (item 1 of pos) & "," & (item 2 of pos) & "," & (item 1 of sz) & "," & (item 2 of sz)
    end tell
end tell
'''
    raw = osascript(script)
    if raw.startswith("Error"):
        return None
    try:
        parts = [int(v.strip()) for v in raw.split(",")]
        return parts[0], parts[1], parts[2], parts[3]
    except Exception:
        return None


def to_screen(x: int, y: int, bounds: tuple | None = None) -> tuple[int, int]:
    """Convert virtual 1000x1000 coords to actual screen coords.

    If bounds (wx, wy, ww, wh) are given, maps relative to that window.
    Otherwise maps to full screen.
    """
    if bounds:
        wx, wy, ww, wh = bounds
        return int(wx + x * ww / VIRTUAL_SIZE), int(wy + y * wh / VIRTUAL_SIZE)
    sw, sh = pyautogui.size()
    return int(x * sw / VIRTUAL_SIZE), int(y * sh / VIRTUAL_SIZE)


_ROLE_PREFIX = {
    "AXButton": "B",
    "AXTextField": "T",
    "AXTextArea": "T",
    "AXCheckBox": "C",
    "AXRadioButton": "R",
    "AXPopUpButton": "P",
    "AXLink": "L",
    "AXComboBox": "P",
    "AXMenuItem": "M",
    "AXStaticText": "S",
}
_ACTIONABLE_ROLES = set(_ROLE_PREFIX.keys())


def fetch_ui_elements(app_name: str) -> list[dict]:
    """Fetch actionable UI elements of the frontmost window via AppleScript."""
    script = f'''
tell application "System Events"
    tell process "{app_name}"
        set output to ""
        try
            set elems to entire contents of window 1
            repeat with e in elems
                try
                    set r to role of e
                    if r is in {{"AXButton", "AXTextField", "AXTextArea", "AXCheckBox", "AXRadioButton", "AXPopUpButton", "AXLink", "AXComboBox", "AXStaticText"}} then
                        set t to ""
                        try
                            set t to name of e
                        end try
                        if t is "" or t is missing value then
                            try
                                set t to value of e as string
                            end try
                        end if
                        if t is missing value then set t to ""
                        set p to position of e
                        set s to size of e
                        if (item 1 of s) > 4 and (item 2 of s) > 4 then
                            set output to output & r & "|" & t & "|" & (item 1 of p) & "," & (item 2 of p) & "|" & (item 1 of s) & "," & (item 2 of s) & "\n"
                        end if
                    end if
                end try
            end repeat
        end try
        return output
    end tell
end tell
'''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=15,
    )
    raw = result.stdout.strip()
    elements = []
    counters: dict[str, int] = {}
    for line in raw.splitlines():
        parts = line.split("|")
        if len(parts) != 4:
            continue
        role, label, pos_str, size_str = parts
        try:
            px, py = [int(v) for v in pos_str.split(",")]
            pw, ph = [int(v) for v in size_str.split(",")]
        except ValueError:
            continue
        prefix = _ROLE_PREFIX.get(role, "E")
        counters[prefix] = counters.get(prefix, 0) + 1
        elem_id = f"{prefix}{counters[prefix]}"
        elements.append({"id": elem_id, "role": role, "label": label.strip(), "x": px, "y": py, "w": pw, "h": ph})
    return elements


def annotate_screenshot(elements: list[dict], app_name: str | None = None):
    """Take screenshot, draw element ID labels, return (PIL Image, cropped bounds or None)."""
    img = pyautogui.screenshot()
    draw = ImageDraw.Draw(img)

    bounds = get_window_bounds(app_name) if app_name else None

    colors = {"B": "#FF3B30", "T": "#007AFF", "C": "#34C759", "R": "#34C759",
              "P": "#FF9500", "L": "#5856D6", "M": "#FF2D55", "S": "#8E8E93", "E": "#636366"}

    for elem in elements:
        eid = elem["id"]
        color = colors.get(eid[0], "#636366")
        x, y, w, h = elem["x"], elem["y"], elem["w"], elem["h"]
        draw.rectangle([x, y, x + w, y + h], outline=color, width=2)
        # ラベル背景
        lx, ly = x, max(0, y - 16)
        label_text = eid
        draw.rectangle([lx, ly, lx + len(label_text) * 8 + 4, ly + 14], fill=color)
        draw.text((lx + 2, ly + 1), label_text, fill="white")

    if bounds:
        wx, wy, ww, wh = bounds
        img = img.crop((wx, wy, wx + ww, wy + wh))

    return img


def screenshot_result(message: str, delay: float = 0.5, app_name: str | None = None) -> list:
    """Return text message + screenshot as MCP content list.

    If app_name is given, crops the screenshot to the app's window.
    """
    time.sleep(delay)
    img = pyautogui.screenshot()

    if app_name:
        bounds = get_window_bounds(app_name)
        if bounds:
            wx, wy, ww, wh = bounds
            img = img.crop((wx, wy, wx + ww, wy + wh))

    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return [
        TextContent(type="text", text=message),
        ImageContent(type="image", data=b64, mimeType="image/png"),
    ]


# ──────────────────────────────────────────
# 要素ベース操作 (Peekaboo方式)
# ──────────────────────────────────────────

@mcp.tool()
def see(app_name: str) -> list:
    """Capture the app window and return an annotated screenshot with element IDs.

    Each actionable UI element is labeled with a short ID:
      B = Button, T = TextField/TextArea, C = CheckBox, R = RadioButton,
      P = PopUp/ComboBox, L = Link, S = StaticText

    Use the returned IDs with click_element to interact without coordinates.
    """
    global _element_cache
    elements = fetch_ui_elements(app_name)
    _element_cache = {e["id"]: (e["x"], e["y"], e["w"], e["h"]) for e in elements}

    img = annotate_screenshot(elements, app_name)
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    lines = [f"{e['id']:4s}  {e['role']:20s}  {e['label'][:40]}" for e in elements]
    summary = f"Found {len(elements)} elements:\n" + "\n".join(lines)

    return [
        TextContent(type="text", text=summary),
        ImageContent(type="image", data=b64, mimeType="image/png"),
    ]


@mcp.tool()
def click_element(element_id: str, app_name: str = "") -> list:
    """Click a UI element by its ID from the last `see` call (e.g. 'B1', 'T2').

    Args:
        element_id: Element ID returned by `see` (e.g. 'B1', 'T2', 'L3').
        app_name: If provided, crops the result screenshot to this app's window.
    """
    bounds = _element_cache.get(element_id.upper())
    if bounds is None:
        return screenshot_result(f"Element '{element_id}' not found. Run `see` first.", delay=0)
    x, y, w, h = bounds
    cx, cy = x + w // 2, y + h // 2
    pyautogui.click(cx, cy)
    return screenshot_result(f"Clicked element {element_id} at ({cx}, {cy})", delay=0.3, app_name=app_name or None)


# ──────────────────────────────────────────
# A: アプリ操作
# ──────────────────────────────────────────

@mcp.tool()
def open_app(app_name: str) -> list:
    """Open an application by name (e.g. 'Safari', 'Finder', 'Slack')."""
    result = subprocess.run(["open", "-a", app_name], capture_output=True, text=True)
    if result.returncode != 0:
        return screenshot_result(f"Error: {result.stderr.strip()}", delay=0)
    return screenshot_result(f"Opened {app_name}", delay=1.0, app_name=app_name)


@mcp.tool()
def quit_app(app_name: str) -> list:
    """Quit an application by name."""
    msg = osascript(f'tell application "{app_name}" to quit')
    return screenshot_result(msg)


@mcp.tool()
def switch_to_app(app_name: str) -> list:
    """Bring an application to the foreground."""
    msg = osascript(f'tell application "{app_name}" to activate')
    return screenshot_result(msg, delay=0.5, app_name=app_name)


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
    return screenshot_result(msg, delay=0.5, app_name=app_name)


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
    return screenshot_result(msg, delay=0.5, app_name=app_name)


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
    return screenshot_result(msg, delay=0.5, app_name=app_name)


@mcp.tool()
def open_finder_folder(path: str) -> list:
    """Open a folder in Finder (e.g. '/Users/example/Desktop')."""
    result = subprocess.run(["open", path], capture_output=True, text=True)
    if result.returncode != 0:
        return screenshot_result(f"Error: {result.stderr.strip()}", delay=0)
    return screenshot_result(f"Opened {path} in Finder", delay=1.0, app_name="Finder")


# ──────────────────────────────────────────
# C: キーボード・マウス自動操作
# ──────────────────────────────────────────

@mcp.tool()
def type_text(text: str, app_name: str = "") -> list:
    """Type the given text into the currently focused input field.

    Args:
        text: Text to type.
        app_name: If provided, crops the result screenshot to this app's window.
    """
    escaped = text.replace('"', '\\"')
    script = f'''
tell application "System Events"
    keystroke "{escaped}"
end tell
'''
    msg = osascript(script)
    return screenshot_result(msg, delay=0.3, app_name=app_name or None)


@mcp.tool()
def send_keystroke(key: str, modifiers: str = "", app_name: str = "") -> list:
    """Send a keyboard shortcut.

    Args:
        key: The key to press (e.g. 'c', 'v', 'return', 'tab', 'escape').
        modifiers: Comma-separated modifiers: 'command', 'shift', 'option', 'control'.
        app_name: If provided, crops the result screenshot to this app's window.
    """
    if modifiers.strip():
        mod_list = [m.strip() + " down" for m in modifiers.split(",") if m.strip()]
        mod_str = "{" + ", ".join(mod_list) + "}"
        script = f'tell application "System Events" to keystroke "{key}" using {mod_str}'
    else:
        script = f'tell application "System Events" to keystroke "{key}"'
    msg = osascript(script)
    return screenshot_result(msg, delay=0.3, app_name=app_name or None)


@mcp.tool()
def press_key(key_code: str, app_name: str = "") -> list:
    """Press a special key by name.

    Supported keys: return, tab, space, delete, escape, up, down, left, right,
    home, end, pageup, pagedown, f1-f12.

    Args:
        key_code: Key name.
        app_name: If provided, crops the result screenshot to this app's window.
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
    return screenshot_result(msg, delay=0.3, app_name=app_name or None)


@mcp.tool()
def press_enter(app_name: str = "") -> list:
    """Press the Enter (Return) key.

    Args:
        app_name: If provided, crops the result screenshot to this app's window.
    """
    msg = osascript('tell application "System Events" to key code 36')
    return screenshot_result(msg, delay=0.3, app_name=app_name or None)


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
def get_mouse_position(app_name: str = "") -> list:
    """Get the current mouse cursor position as virtual 1000x1000 coordinates.

    If app_name is provided, coordinates are relative to that app's window.
    """
    ax, ay = pyautogui.position()
    bounds = get_window_bounds(app_name) if app_name else None
    if bounds:
        wx, wy, ww, wh = bounds
        vx = int((ax - wx) * VIRTUAL_SIZE / ww)
        vy = int((ay - wy) * VIRTUAL_SIZE / wh)
    else:
        sw, sh = pyautogui.size()
        vx = int(ax * VIRTUAL_SIZE / sw)
        vy = int(ay * VIRTUAL_SIZE / sh)
    return screenshot_result(f"virtual=({vx}, {vy})  actual=({ax}, {ay})", delay=0, app_name=app_name or None)


@mcp.tool()
def mouse_move(x: int, y: int, app_name: str = "", duration: float = 0.3) -> list:
    """Move the mouse cursor to (x, y) in virtual 1000x1000 coordinates.

    Args:
        x: Horizontal position (0-1000).
        y: Vertical position (0-1000).
        app_name: If provided, coordinates are relative to this app's window.
        duration: Time in seconds for the movement (default 0.3).
    """
    bounds = get_window_bounds(app_name) if app_name else None
    sx, sy = to_screen(x, y, bounds)
    pyautogui.moveTo(sx, sy, duration=duration)
    return screenshot_result(f"Moved to virtual=({x}, {y})", delay=0.2, app_name=app_name or None)


@mcp.tool()
def mouse_click(x: int, y: int, app_name: str = "", button: str = "left") -> list:
    """Click at the given position in virtual 1000x1000 coordinates.

    Args:
        x: Horizontal position (0-1000).
        y: Vertical position (0-1000).
        app_name: If provided, coordinates are relative to this app's window.
        button: 'left', 'right', or 'double' (default 'left').
    """
    bounds = get_window_bounds(app_name) if app_name else None
    sx, sy = to_screen(x, y, bounds)
    if button == "double":
        pyautogui.doubleClick(sx, sy)
    elif button == "right":
        pyautogui.rightClick(sx, sy)
    else:
        pyautogui.click(sx, sy)
    return screenshot_result(f"{button} click at virtual=({x}, {y})", delay=0.3, app_name=app_name or None)


@mcp.tool()
def mouse_drag(from_x: int, from_y: int, to_x: int, to_y: int, app_name: str = "", duration: float = 0.5) -> list:
    """Drag from one position to another in virtual 1000x1000 coordinates.

    Args:
        from_x: Start horizontal position (0-1000).
        from_y: Start vertical position (0-1000).
        to_x: End horizontal position (0-1000).
        to_y: End vertical position (0-1000).
        app_name: If provided, coordinates are relative to this app's window.
        duration: Time in seconds for the drag (default 0.5).
    """
    bounds = get_window_bounds(app_name) if app_name else None
    sfx, sfy = to_screen(from_x, from_y, bounds)
    stx, sty = to_screen(to_x, to_y, bounds)
    pyautogui.moveTo(sfx, sfy, duration=0.2)
    pyautogui.dragTo(stx, sty, duration=duration, button="left")
    return screenshot_result(f"Dragged from virtual=({from_x}, {from_y}) to ({to_x}, {to_y})", delay=0.3, app_name=app_name or None)


@mcp.tool()
def mouse_scroll(amount: int, x: int = None, y: int = None, app_name: str = "") -> list:
    """Scroll up or down at the current or specified position.

    Args:
        amount: Positive to scroll up, negative to scroll down.
        x: Optional horizontal position (0-1000) to scroll at.
        y: Optional vertical position (0-1000) to scroll at.
        app_name: If provided, coordinates are relative to this app's window.
    """
    if x is not None and y is not None:
        bounds = get_window_bounds(app_name) if app_name else None
        sx, sy = to_screen(x, y, bounds)
        pyautogui.moveTo(sx, sy, duration=0.2)
    pyautogui.scroll(amount)
    direction = "up" if amount > 0 else "down"
    return screenshot_result(f"Scrolled {direction} by {abs(amount)}", delay=0.3, app_name=app_name or None)


@mcp.tool()
def get_screen_size() -> list:
    """Get the screen resolution (width x height)."""
    w, h = pyautogui.size()
    return screenshot_result(f"width={w}, height={h}", delay=0)


if __name__ == "__main__":
    mcp.run(transport="stdio")
