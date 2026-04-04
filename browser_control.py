from pathlib import Path
from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

mcp = FastMCP("browser-control")

_playwright: Playwright | None = None
_browser: Browser | None = None
_context: BrowserContext | None = None
_pages: list[Page] = []
_current_page_index: int = 0


async def get_context() -> BrowserContext:
    global _playwright, _browser, _context
    if _playwright is None:
        _playwright = await async_playwright().start()
    if _browser is None or not _browser.is_connected():
        _browser = await _playwright.chromium.launch(headless=False)
    if _context is None:
        _context = await _browser.new_context()
    return _context


async def get_page() -> Page:
    global _pages, _current_page_index
    context = await get_context()
    if not _pages:
        page = await context.new_page()
        _pages.append(page)
        _current_page_index = 0
    page = _pages[_current_page_index]
    if page.is_closed():
        _pages.pop(_current_page_index)
        if not _pages:
            page = await context.new_page()
            _pages.append(page)
            _current_page_index = 0
        else:
            _current_page_index = min(_current_page_index, len(_pages) - 1)
        page = _pages[_current_page_index]
    return page


# ── ナビゲーション ──────────────────────────────────────────

@mcp.tool()
async def open_url(url: str) -> str:
    """指定したURLをブラウザで開く。"""
    page = await get_page()
    await page.goto(url)
    return f"opened: {page.url}"


@mcp.tool()
async def search_google(query: str) -> str:
    """Googleで指定したキーワードを検索する。"""
    page = await get_page()
    await page.goto(f"https://www.google.com/search?q={query}")
    return f"searched: {query}"


@mcp.tool()
async def go_back() -> str:
    """ブラウザの戻るボタンを押す。"""
    page = await get_page()
    await page.go_back()
    return f"went back to: {page.url}"


@mcp.tool()
async def go_forward() -> str:
    """ブラウザの進むボタンを押す。"""
    page = await get_page()
    await page.go_forward()
    return f"went forward to: {page.url}"


@mcp.tool()
async def reload_page() -> str:
    """現在のページをリロードする。"""
    page = await get_page()
    await page.reload()
    return f"reloaded: {page.url}"


# ── タブ管理 ───────────────────────────────────────────────

@mcp.tool()
async def new_tab(url: str = "") -> str:
    """新しいタブを開く。URLを指定すると開いた後に遷移する。"""
    global _pages, _current_page_index
    context = await get_context()
    page = await context.new_page()
    _pages.append(page)
    _current_page_index = len(_pages) - 1
    if url:
        await page.goto(url)
        return f"new tab opened: {page.url}"
    return f"new tab opened (tab index: {_current_page_index})"


@mcp.tool()
async def close_tab(index: int = -1) -> str:
    """指定したインデックスのタブを閉じる。-1で現在のタブを閉じる。"""
    global _pages, _current_page_index
    if not _pages:
        return "no tabs open"
    target = _current_page_index if index == -1 else index
    if target < 0 or target >= len(_pages):
        return f"invalid tab index: {target}"
    await _pages[target].close()
    _pages.pop(target)
    if not _pages:
        _current_page_index = 0
    else:
        _current_page_index = min(target, len(_pages) - 1)
    return f"closed tab {target}, now on tab {_current_page_index}"


@mcp.tool()
async def switch_tab(index: int) -> str:
    """指定したインデックスのタブに切り替える。"""
    global _current_page_index
    if index < 0 or index >= len(_pages):
        return f"invalid tab index: {index} (total: {len(_pages)})"
    _current_page_index = index
    page = _pages[index]
    await page.bring_to_front()
    return f"switched to tab {index}: {page.url}"


@mcp.tool()
async def list_tabs() -> str:
    """開いているタブの一覧を返す。"""
    if not _pages:
        return "no tabs open"
    result = []
    for i, page in enumerate(_pages):
        marker = " (current)" if i == _current_page_index else ""
        result.append(f"[{i}] {page.url}{marker}")
    return "\n".join(result)


# ── 情報取得 ───────────────────────────────────────────────

@mcp.tool()
async def get_current_url() -> str:
    """現在のページのURLを取得する。"""
    page = await get_page()
    return page.url


@mcp.tool()
async def get_page_title() -> str:
    """現在のページのタイトルを取得する。"""
    page = await get_page()
    return await page.title()


@mcp.tool()
async def get_page_content() -> str:
    """現在のページの本文テキストを取得する（最大3000文字）。"""
    page = await get_page()
    content = await page.inner_text("body")
    return content[:3000]


@mcp.tool()
async def get_page_html() -> str:
    """現在のページのHTMLソースを取得する（最大5000文字）。"""
    page = await get_page()
    html = await page.content()
    return html[:5000]


@mcp.tool()
async def get_links() -> str:
    """現在のページのリンク一覧（テキストとURL）を取得する。"""
    page = await get_page()
    links = await page.eval_on_selector_all(
        "a[href]",
        "elements => elements.map(e => ({ text: e.innerText.trim(), href: e.href }))"
    )
    result = [f"{l['text'] or '(no text)'}: {l['href']}" for l in links[:50]]
    return "\n".join(result) if result else "no links found"


@mcp.tool()
async def get_element_text(selector: str) -> str:
    """CSSセレクターで指定した要素のテキストを取得する。"""
    page = await get_page()
    text = await page.inner_text(selector)
    return text


@mcp.tool()
async def get_element_attribute(selector: str, attribute: str) -> str:
    """CSSセレクターで指定した要素の属性値を取得する。"""
    page = await get_page()
    value = await page.get_attribute(selector, attribute)
    return value or f"attribute '{attribute}' not found"


# ── クリック・入力操作 ────────────────────────────────────

@mcp.tool()
async def click_element(selector: str) -> str:
    """CSSセレクターで指定した要素をクリックする。"""
    page = await get_page()
    await page.click(selector)
    return f"clicked: {selector}"


@mcp.tool()
async def find_and_click(text: str) -> str:
    """ページ内のテキストで要素を見つけてクリックする。"""
    page = await get_page()
    await page.get_by_text(text).first.click()
    return f"clicked element with text: {text}"


@mcp.tool()
async def hover_element(selector: str) -> str:
    """CSSセレクターで指定した要素にマウスをホバーする。"""
    page = await get_page()
    await page.hover(selector)
    return f"hovered: {selector}"


@mcp.tool()
async def type_text(selector: str, text: str) -> str:
    """指定したセレクターの入力欄にテキストを入力する（既存の内容を置き換える）。"""
    page = await get_page()
    await page.fill(selector, text)
    return f"typed '{text}' into {selector}"


@mcp.tool()
async def press_key(key: str) -> str:
    """キーボードのキーを押す。例: Enter, Tab, Escape, ArrowDown, Control+a"""
    page = await get_page()
    await page.keyboard.press(key)
    return f"pressed: {key}"


@mcp.tool()
async def select_option(selector: str, value: str) -> str:
    """セレクトボックスで指定した値を選択する。"""
    page = await get_page()
    await page.select_option(selector, value=value)
    return f"selected '{value}' in {selector}"


@mcp.tool()
async def check_checkbox(selector: str, checked: bool = True) -> str:
    """チェックボックスをON/OFFにする。checked=TrueでON、FalseでOFF。"""
    page = await get_page()
    if checked:
        await page.check(selector)
    else:
        await page.uncheck(selector)
    state = "checked" if checked else "unchecked"
    return f"{state}: {selector}"


@mcp.tool()
async def drag_and_drop(source_selector: str, target_selector: str) -> str:
    """ソース要素をターゲット要素にドラッグ＆ドロップする。"""
    page = await get_page()
    await page.drag_and_drop(source_selector, target_selector)
    return f"dragged '{source_selector}' to '{target_selector}'"


# ── スクロール・スクリーンショット ──────────────────────────

@mcp.tool()
async def scroll_page(direction: str = "down", amount: int = 500) -> str:
    """ページをスクロールする。direction: up または down、amount: ピクセル数"""
    page = await get_page()
    y = amount if direction == "down" else -amount
    await page.evaluate(f"window.scrollBy(0, {y})")
    return f"scrolled {direction} by {amount}px"


@mcp.tool()
async def scroll_to_element(selector: str) -> str:
    """指定した要素までスクロールする。"""
    page = await get_page()
    await page.locator(selector).scroll_into_view_if_needed()
    return f"scrolled to: {selector}"


@mcp.tool()
async def take_screenshot() -> str:
    """現在のページのスクリーンショットを撮ってデスクトップに保存する。"""
    page = await get_page()
    path = str(Path.home() / "Desktop" / "screenshot.png")
    await page.screenshot(path=path, full_page=False)
    return f"screenshot saved: {path}"


@mcp.tool()
async def take_full_screenshot() -> str:
    """ページ全体（スクロール込み）のスクリーンショットをデスクトップに保存する。"""
    page = await get_page()
    path = str(Path.home() / "Desktop" / "screenshot_full.png")
    await page.screenshot(path=path, full_page=True)
    return f"full screenshot saved: {path}"


# ── 待機・制御 ─────────────────────────────────────────────

@mcp.tool()
async def wait_for_element(selector: str, timeout: int = 10000) -> str:
    """指定した要素が表示されるまで待機する。timeout: ミリ秒（デフォルト10秒）"""
    page = await get_page()
    await page.wait_for_selector(selector, timeout=timeout)
    return f"element appeared: {selector}"


@mcp.tool()
async def wait_for_load() -> str:
    """ページの読み込みが完了するまで待機する。"""
    page = await get_page()
    await page.wait_for_load_state("load")
    return f"page loaded: {page.url}"


@mcp.tool()
async def wait_seconds(seconds: float) -> str:
    """指定した秒数だけ待機する。"""
    import asyncio
    await asyncio.sleep(seconds)
    return f"waited {seconds} seconds"


# ── JavaScript実行 ─────────────────────────────────────────

@mcp.tool()
async def execute_javascript(script: str) -> str:
    """ページ上で任意のJavaScriptを実行し、結果を返す。"""
    page = await get_page()
    result = await page.evaluate(script)
    return str(result)


# ── クッキー・ストレージ ───────────────────────────────────

@mcp.tool()
async def get_cookies() -> str:
    """現在のページのクッキー一覧を取得する。"""
    context = await get_context()
    cookies = await context.cookies()
    result = [f"{c['name']}={c['value']} (domain: {c['domain']})" for c in cookies]
    return "\n".join(result) if result else "no cookies"


@mcp.tool()
async def clear_cookies() -> str:
    """すべてのクッキーを削除する。"""
    context = await get_context()
    await context.clear_cookies()
    return "cookies cleared"


@mcp.tool()
async def get_local_storage(key: str) -> str:
    """ローカルストレージから指定したキーの値を取得する。"""
    page = await get_page()
    value = await page.evaluate(f"localStorage.getItem('{key}')")
    return str(value) if value is not None else f"key '{key}' not found"


@mcp.tool()
async def set_local_storage(key: str, value: str) -> str:
    """ローカルストレージに指定したキーと値を保存する。"""
    page = await get_page()
    await page.evaluate(f"localStorage.setItem('{key}', '{value}')")
    return f"set localStorage['{key}'] = '{value}'"


@mcp.tool()
async def clear_local_storage() -> str:
    """ローカルストレージをすべてクリアする。"""
    page = await get_page()
    await page.evaluate("localStorage.clear()")
    return "localStorage cleared"


# ── ネットワーク傍受 ───────────────────────────────────────

_intercepted_requests: list[dict] = []


@mcp.tool()
async def start_network_intercept() -> str:
    """ネットワークリクエストの傍受を開始する。"""
    page = await get_page()
    _intercepted_requests.clear()

    def handle_request(request):
        _intercepted_requests.append({
            "method": request.method,
            "url": request.url,
        })

    page.on("request", handle_request)
    return "network intercept started"


@mcp.tool()
async def get_intercepted_requests() -> str:
    """傍受したネットワークリクエストの一覧を返す（最大50件）。"""
    if not _intercepted_requests:
        return "no requests intercepted (call start_network_intercept first)"
    result = [f"{r['method']} {r['url']}" for r in _intercepted_requests[:50]]
    return "\n".join(result)


# ── PDF保存 ────────────────────────────────────────────────

@mcp.tool()
async def save_as_pdf() -> str:
    """現在のページをPDFとしてデスクトップに保存する。"""
    page = await get_page()
    path = str(Path.home() / "Desktop" / "page.pdf")
    await page.pdf(path=path)
    return f"PDF saved: {path}"


# ── ファイルアップロード ────────────────────────────────────

@mcp.tool()
async def upload_file(selector: str, file_path: str) -> str:
    """input[type=file]要素にファイルをアップロードする。"""
    page = await get_page()
    await page.set_input_files(selector, file_path)
    return f"uploaded '{file_path}' to {selector}"


# ── ダイアログ処理 ─────────────────────────────────────────

@mcp.tool()
async def handle_dialog(accept: bool = True, prompt_text: str = "") -> str:
    """次に表示されるalert/confirm/promptダイアログを自動処理する。accept=TrueでOK、FalseでキャンセL。"""
    page = await get_page()

    async def on_dialog(dialog):
        if prompt_text and dialog.type == "prompt":
            await dialog.accept(prompt_text)
        elif accept:
            await dialog.accept()
        else:
            await dialog.dismiss()

    page.once("dialog", on_dialog)
    action = "accept" if accept else "dismiss"
    return f"next dialog will be {action}ed"


# ── 座標クリック・右クリック ───────────────────────────────

@mcp.tool()
async def click_at(x: int, y: int) -> str:
    """指定したX/Y座標をクリックする。"""
    page = await get_page()
    await page.mouse.click(x, y)
    return f"clicked at ({x}, {y})"


@mcp.tool()
async def right_click(selector: str) -> str:
    """CSSセレクターで指定した要素を右クリックする。"""
    page = await get_page()
    await page.click(selector, button="right")
    return f"right-clicked: {selector}"


@mcp.tool()
async def double_click(selector: str) -> str:
    """CSSセレクターで指定した要素をダブルクリックする。"""
    page = await get_page()
    await page.dbl_click(selector)
    return f"double-clicked: {selector}"


# ── ビューポート変更 ───────────────────────────────────────

@mcp.tool()
async def set_viewport(width: int, height: int) -> str:
    """ブラウザのビューポートサイズを変更する。例: 375x812でスマホ表示。"""
    page = await get_page()
    await page.set_viewport_size({"width": width, "height": height})
    return f"viewport set to {width}x{height}"


@mcp.tool()
async def set_mobile_view() -> str:
    """ビューポートをiPhone 14サイズ（390x844）に変更する。"""
    page = await get_page()
    await page.set_viewport_size({"width": 390, "height": 844})
    return "viewport set to mobile (390x844)"


@mcp.tool()
async def set_desktop_view() -> str:
    """ビューポートをデスクトップサイズ（1280x800）に変更する。"""
    page = await get_page()
    await page.set_viewport_size({"width": 1280, "height": 800})
    return "viewport set to desktop (1280x800)"


# ── iframe操作 ─────────────────────────────────────────────

@mcp.tool()
async def click_in_iframe(iframe_selector: str, element_selector: str) -> str:
    """iframe内の要素をクリックする。"""
    page = await get_page()
    frame = page.frame_locator(iframe_selector)
    await frame.locator(element_selector).click()
    return f"clicked '{element_selector}' inside iframe '{iframe_selector}'"


@mcp.tool()
async def type_in_iframe(iframe_selector: str, element_selector: str, text: str) -> str:
    """iframe内の入力欄にテキストを入力する。"""
    page = await get_page()
    frame = page.frame_locator(iframe_selector)
    await frame.locator(element_selector).fill(text)
    return f"typed '{text}' into '{element_selector}' inside iframe '{iframe_selector}'"


# ── 要素確認 ───────────────────────────────────────────────

@mcp.tool()
async def element_exists(selector: str) -> str:
    """指定したセレクターの要素がページ上に存在するか確認する。"""
    page = await get_page()
    count = await page.locator(selector).count()
    return f"exists: {count > 0} (found {count} element(s))"


@mcp.tool()
async def element_is_visible(selector: str) -> str:
    """指定したセレクターの要素が表示されているか確認する。"""
    page = await get_page()
    visible = await page.is_visible(selector)
    return f"visible: {visible}"


@mcp.tool()
async def element_is_enabled(selector: str) -> str:
    """指定したセレクターの要素が有効（操作可能）か確認する。"""
    page = await get_page()
    enabled = await page.is_enabled(selector)
    return f"enabled: {enabled}"


# ── 複数要素・構造化データ取得 ────────────────────────────

@mcp.tool()
async def get_all_elements_text(selector: str) -> str:
    """同一セレクターにマッチするすべての要素のテキストを取得する。"""
    page = await get_page()
    texts = await page.eval_on_selector_all(
        selector,
        "elements => elements.map(e => e.innerText.trim())"
    )
    result = [f"[{i}] {t}" for i, t in enumerate(texts[:50])]
    return "\n".join(result) if result else "no elements found"


@mcp.tool()
async def get_table_data(selector: str = "table") -> str:
    """tableタグのデータをCSV形式で取得する。"""
    page = await get_page()
    data = await page.eval_on_selector(
        selector,
        """table => {
            const rows = Array.from(table.querySelectorAll('tr'));
            return rows.map(row =>
                Array.from(row.querySelectorAll('th,td'))
                    .map(cell => cell.innerText.trim().replace(/,/g, ''))
                    .join(',')
            ).join('\\n');
        }"""
    )
    return data


@mcp.tool()
async def get_images() -> str:
    """現在のページの画像URL一覧を取得する（最大50件）。"""
    page = await get_page()
    images = await page.eval_on_selector_all(
        "img[src]",
        "elements => elements.map(e => ({ alt: e.alt, src: e.src }))"
    )
    result = [f"{img['alt'] or '(no alt)'}: {img['src']}" for img in images[:50]]
    return "\n".join(result) if result else "no images found"


@mcp.tool()
async def get_meta_tags() -> str:
    """現在のページのメタタグ情報（OGP・description等）を取得する。"""
    page = await get_page()
    metas = await page.eval_on_selector_all(
        "meta",
        "elements => elements.map(e => ({ name: e.name || e.property || e.httpEquiv, content: e.content }))"
    )
    result = [f"{m['name']}: {m['content']}" for m in metas if m['name'] and m['content']]
    return "\n".join(result) if result else "no meta tags found"


# ── セッションストレージ ───────────────────────────────────

@mcp.tool()
async def get_session_storage(key: str) -> str:
    """セッションストレージから指定したキーの値を取得する。"""
    page = await get_page()
    value = await page.evaluate(f"sessionStorage.getItem('{key}')")
    return str(value) if value is not None else f"key '{key}' not found"


@mcp.tool()
async def set_session_storage(key: str, value: str) -> str:
    """セッションストレージに指定したキーと値を保存する。"""
    page = await get_page()
    await page.evaluate(f"sessionStorage.setItem('{key}', '{value}')")
    return f"set sessionStorage['{key}'] = '{value}'"


@mcp.tool()
async def clear_session_storage() -> str:
    """セッションストレージをすべてクリアする。"""
    page = await get_page()
    await page.evaluate("sessionStorage.clear()")
    return "sessionStorage cleared"


# ── クリップボード ─────────────────────────────────────────

@mcp.tool()
async def copy_text_to_clipboard(text: str) -> str:
    """指定したテキストをクリップボードにコピーする。"""
    page = await get_page()
    await page.evaluate(f"navigator.clipboard.writeText('{text}')")
    return f"copied to clipboard: {text}"


@mcp.tool()
async def get_selected_text() -> str:
    """ページ上で現在選択されているテキストを取得する。"""
    page = await get_page()
    text = await page.evaluate("window.getSelection().toString()")
    return text if text else "no text selected"


# ── 要素操作（拡張） ──────────────────────────────────────

@mcp.tool()
async def screenshot_element(selector: str) -> str:
    """指定した要素だけのスクリーンショットをデスクトップに保存する。"""
    page = await get_page()
    path = str(Path.home() / "Desktop" / "element_screenshot.png")
    await page.locator(selector).screenshot(path=path)
    return f"element screenshot saved: {path}"


@mcp.tool()
async def get_element_bounding_box(selector: str) -> str:
    """指定した要素の位置（x, y）とサイズ（width, height）を取得する。"""
    page = await get_page()
    box = await page.locator(selector).bounding_box()
    if box is None:
        return f"element not found or not visible: {selector}"
    return f"x={box['x']:.0f}, y={box['y']:.0f}, width={box['width']:.0f}, height={box['height']:.0f}"


@mcp.tool()
async def focus_element(selector: str) -> str:
    """指定した要素にフォーカスを当てる。"""
    page = await get_page()
    await page.focus(selector)
    return f"focused: {selector}"


@mcp.tool()
async def get_element_html(selector: str) -> str:
    """指定した要素のHTMLを取得する。"""
    page = await get_page()
    html = await page.inner_html(selector)
    return html[:3000]


@mcp.tool()
async def highlight_element(selector: str) -> str:
    """指定した要素を赤枠でハイライト表示する（デバッグ用）。"""
    page = await get_page()
    await page.evaluate(
        f"""
        const el = document.querySelector('{selector}');
        if (el) {{
            el.style.outline = '3px solid red';
            el.style.outlineOffset = '2px';
        }}
        """
    )
    return f"highlighted: {selector}"


@mcp.tool()
async def clear_highlight(selector: str) -> str:
    """指定した要素のハイライトを解除する。"""
    page = await get_page()
    await page.evaluate(
        f"""
        const el = document.querySelector('{selector}');
        if (el) {{
            el.style.outline = '';
            el.style.outlineOffset = '';
        }}
        """
    )
    return f"highlight cleared: {selector}"


# ── フォーム ───────────────────────────────────────────────

@mcp.tool()
async def fill_form(fields: str) -> str:
    """JSON形式でフォームを一括入力する。例: {\"#name\": \"John\", \"#email\": \"a@b.com\"}"""
    import json
    page = await get_page()
    data = json.loads(fields)
    results = []
    for selector, value in data.items():
        await page.fill(selector, str(value))
        results.append(f"filled {selector} = {value}")
    return "\n".join(results)


@mcp.tool()
async def get_form_values(form_selector: str = "form") -> str:
    """フォームの現在の入力値を一括取得する。"""
    page = await get_page()
    values = await page.evaluate(
        f"""
        const form = document.querySelector('{form_selector}');
        if (!form) return {{}};
        const result = {{}};
        for (const el of form.elements) {{
            if (el.name) result[el.name] = el.value;
        }}
        return result;
        """
    )
    if not values:
        return "no form or no fields found"
    return "\n".join([f"{k}: {v}" for k, v in values.items()])


@mcp.tool()
async def submit_form(selector: str = "form") -> str:
    """指定したフォームを送信する。"""
    page = await get_page()
    await page.evaluate(f"document.querySelector('{selector}').submit()")
    return f"submitted form: {selector}"


@mcp.tool()
async def clear_form(form_selector: str = "form") -> str:
    """フォームのすべての入力欄をクリアする。"""
    page = await get_page()
    await page.evaluate(
        f"""
        const form = document.querySelector('{form_selector}');
        if (form) form.reset();
        """
    )
    return f"cleared form: {form_selector}"


# ── ブラウザ設定 ───────────────────────────────────────────

@mcp.tool()
async def set_user_agent(user_agent: str) -> str:
    """User-Agentを変更する。変更後はページをリロードすると反映される。"""
    global _context, _pages, _current_page_index
    context = await get_context()
    current_url = _pages[_current_page_index].url if _pages else ""
    await context.close()
    _context = await _browser.new_context(user_agent=user_agent)
    _pages = []
    page = await _context.new_page()
    _pages.append(page)
    _current_page_index = 0
    if current_url and current_url != "about:blank":
        await page.goto(current_url)
    return f"user agent set to: {user_agent}"


@mcp.tool()
async def set_mobile_user_agent() -> str:
    """User-AgentをiPhone（Safari）に変更する。"""
    ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    return await set_user_agent(ua)


@mcp.tool()
async def set_geolocation(latitude: float, longitude: float) -> str:
    """GPS位置情報を偽装する。ページのリロード後に反映される。"""
    context = await get_context()
    await context.set_geolocation({"latitude": latitude, "longitude": longitude})
    await context.grant_permissions(["geolocation"])
    return f"geolocation set to ({latitude}, {longitude})"


@mcp.tool()
async def set_dark_mode() -> str:
    """ページをダークモードで表示する。"""
    page = await get_page()
    await page.emulate_media(color_scheme="dark")
    return "dark mode enabled"


@mcp.tool()
async def set_light_mode() -> str:
    """ページをライトモードで表示する。"""
    page = await get_page()
    await page.emulate_media(color_scheme="light")
    return "light mode enabled"


@mcp.tool()
async def set_zoom(scale: float) -> str:
    """ページのズーム倍率を変更する。例: 1.5で150%、0.5で50%。"""
    page = await get_page()
    await page.evaluate(f"document.body.style.zoom = '{scale}'")
    return f"zoom set to {int(scale * 100)}%"


# ── デバッグ ───────────────────────────────────────────────

_console_logs: list[str] = []


@mcp.tool()
async def start_console_log() -> str:
    """ブラウザのコンソールログの収集を開始する。"""
    page = await get_page()
    _console_logs.clear()

    def handle_console(msg):
        _console_logs.append(f"[{msg.type}] {msg.text}")

    page.on("console", handle_console)
    return "console log collection started"


@mcp.tool()
async def get_console_logs() -> str:
    """収集したコンソールログを返す（最大100件）。"""
    if not _console_logs:
        return "no logs (call start_console_log first)"
    return "\n".join(_console_logs[:100])


@mcp.tool()
async def measure_load_time(url: str) -> str:
    """指定したURLのページ読み込み時間を計測する。"""
    import time
    page = await get_page()
    start = time.time()
    await page.goto(url, wait_until="load")
    elapsed = time.time() - start
    perf = await page.evaluate(
        "JSON.stringify(performance.getEntriesByType('navigation')[0])"
    )
    import json
    nav = json.loads(perf)
    dom_content = nav.get("domContentLoadedEventEnd", 0) - nav.get("startTime", 0)
    return (
        f"total: {elapsed:.2f}s\n"
        f"DOMContentLoaded: {dom_content:.0f}ms\n"
        f"url: {page.url}"
    )


@mcp.tool()
async def get_page_errors() -> str:
    """ページで発生したJavaScriptエラーを収集・返す。事前にstart_console_logが必要。"""
    errors = [log for log in _console_logs if log.startswith("[error]")]
    return "\n".join(errors) if errors else "no errors found"


@mcp.tool()
async def check_broken_links() -> str:
    """現在のページ内のリンクをチェックし、アクセス不可のものを返す（最大20件）。"""
    import asyncio
    page = await get_page()
    links = await page.eval_on_selector_all(
        "a[href]",
        "elements => elements.map(e => e.href).filter(h => h.startsWith('http'))"
    )
    links = list(set(links[:20]))
    context = await get_context()
    broken = []
    for link in links:
        try:
            check_page = await context.new_page()
            response = await check_page.goto(link, timeout=5000)
            if response and response.status >= 400:
                broken.append(f"{response.status}: {link}")
            await check_page.close()
        except Exception:
            broken.append(f"unreachable: {link}")
    return "\n".join(broken) if broken else "all links ok"


# ── ブラウザ終了 ───────────────────────────────────────────

@mcp.tool()
async def close_browser() -> str:
    """ブラウザを完全に閉じる。"""
    global _playwright, _browser, _context, _pages, _current_page_index
    if _browser:
        await _browser.close()
        _browser = None
        _context = None
        _pages = []
        _current_page_index = 0
    if _playwright:
        await _playwright.stop()
        _playwright = None
    return "browser closed"


mcp.run(transport="stdio")
