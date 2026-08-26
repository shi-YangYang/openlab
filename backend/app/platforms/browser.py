"""Browser helpers for login flow and logged-in search.

Browser automation is blocking IO, so every function here is synchronous and
intended to run inside a worker thread (``threading`` / ``asyncio.to_thread``)
rather than on the FastAPI event loop. ``playwright.sync_api`` is imported
lazily so that the backend still starts when Playwright is not installed.
"""
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from .sessions import (
    EXPIRED,
    LOGGED_IN,
    NOT_LOGGED_IN,
    LoginExpiredError,
    LoginRequiredError,
    load_state,
    save_state,
    set_state,
)


def _import_sync_playwright():
    """Return ``playwright.sync_api.sync_playwright`` lazily."""
    from playwright.sync_api import sync_playwright  # noqa: PLC0415
    return sync_playwright

LOGIN_TIMEOUT_SECONDS = 300  # 5 minutes (NFR-3)

# A realistic desktop Chrome UA. The default Playwright headless UA contains
# "HeadlessChrome", which CNKI / Baidu detect and block (returning an empty
# page); using a real UA makes the headless browser pass.
CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Patches applied before every page load (including popups/target=_blank) to
# hide automation markers. `navigator.webdriver` must be hidden on every page,
# otherwise Baidu / CNKI block the newly opened tab with an empty page.
_STEALTH_SCRIPT = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    "window.chrome = window.chrome || { runtime: {} };"
    "Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN','zh','en']});"
    "Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});"
)

# In-progress headed login sessions, keyed by platform. Populated by
# ``run_login`` and consumed by ``complete_login`` / ``cancel_login``.
_login_sessions: Dict[str, Dict[str, Any]] = {}
_login_lock = threading.Lock()

# Search pages that trigger the anti-bot verification when a fresh (unverified)
# browser opens them. The user completes verification in the headed browser.
LOGIN_URLS = {
    "cnki": "https://kns.cnki.net/kns8s/defaultresult/index?kw=test",
    "baidu_xueshu": "https://xueshu.baidu.com/s?wd=test",
}

SEARCH_URL_TEMPLATES = {
    "cnki": "https://kns.cnki.net/kns8s/defaultresult/index?kw={query}",
    "baidu_xueshu": "https://xueshu.baidu.com/s?wd={query}",
}

# Platforms whose login browser must run as a NON-incognito (persistent)
# context. In an incognito ``new_context``, ``target="_blank"`` links open a
# stuck ``about:blank``/``chrome://new-tab-page`` tab (Baidu Xueshu). A
# persistent context opens a normal new tab that navigates correctly.
PERSISTENT_PLATFORMS = {"baidu_xueshu"}

# Detection markers: a page is still "verification" when the URL contains one
# of these fragments or the title contains one of these words.
_VERIFY_URL_MARKERS = ("/verify/", "captcha", "wappass", "validate", "security")
_VERIFY_TITLE_MARKERS = ("验证", "安全", "captcha", "verify", "滑动")


def is_verification_page(url: str = "", title: str = "") -> bool:
    """Return True when the page still looks like an anti-bot verification page."""
    low_url = (url or "").lower()
    low_title = (title or "").lower()
    if any(marker in low_url for marker in _VERIFY_URL_MARKERS):
        return True
    if any(marker.lower() in low_title for marker in _VERIFY_TITLE_MARKERS):
        return True
    return False


def run_login(platform: str, timeout_seconds: int = LOGIN_TIMEOUT_SECONDS) -> None:
    """Launch a headed browser and keep it open until the user finishes.

    Runs in a thread. The browser window stays open so the user can complete the
    platform login; ``complete_login`` / ``cancel_login`` signal completion via
    events, and this function (in the same thread that owns the Playwright
    objects) saves the storage state and closes the window. Playwright's sync
    API is not thread-safe, so the save must happen here rather than in the
    endpoint thread.
    """
    url = LOGIN_URLS.get(platform)
    if url is None:
        set_state(platform, NOT_LOGGED_IN)
        return

    done_event = threading.Event()
    finished_event = threading.Event()
    session: Dict[str, Any] = {"success": False}
    with _login_lock:
        _login_sessions[platform] = {
            "done": done_event,
            "finished": finished_event,
            "session": session,
        }

    pw = None
    browser = None
    context = None
    page = None
    persistent = platform in PERSISTENT_PLATFORMS
    try:
        sync_playwright = _import_sync_playwright()

        pw = sync_playwright().start()
        if persistent:
            # Non-incognito persistent context so target=_blank links open a
            # normal navigable tab (Baidu Xueshu). Uses the bundled Chromium,
            # not the real Chrome channel, so no system Chrome is required.
            user_dir = tempfile.mkdtemp(prefix="openlab-browser-")
            context = pw.chromium.launch_persistent_context(
                user_data_dir=user_dir,
                headless=False,
                viewport={"width": 1366, "height": 768},
                locale="zh-CN",
            )
            context.add_init_script(_STEALTH_SCRIPT)
            # Attach a "page" listener so Playwright tracks popups and
            # user-opened tabs; without it, target=_blank links and manually
            # opened tabs hang on a blank/loading page.
            context.on("page", lambda _p: None)
            page = context.pages[0] if context.pages else context.new_page()
        else:
            browser = pw.chromium.launch(headless=False)
            context = browser.new_context(
                user_agent=CHROME_UA,
                viewport={"width": 1366, "height": 768},
                locale="zh-CN",
            )
            context.add_init_script(_STEALTH_SCRIPT)
            page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        with _login_lock:
            entry = _login_sessions.get(platform)
            if entry is not None:
                entry["context"] = context
    except Exception:  # noqa: BLE001 - launch failure is not fatal
        try:
            if browser is not None:
                browser.close()
            elif context is not None:
                context.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if pw is not None:
                pw.stop()
        except Exception:  # noqa: BLE001
            pass
        set_state(platform, NOT_LOGGED_IN)
        with _login_lock:
            _login_sessions.pop(platform, None)
        finished_event.set()
        return

    try:
        # Wait for the user to finish. We must NOT block the thread with a plain
        # ``threading.Event.wait``: that would stall Playwright's event loop and
        # leave ``target="_blank"`` popups / user-opened tabs stuck on a blank
        # page. Instead we drive Playwright's loop with ``wait_for_timeout`` and
        # poll the event on short intervals.
        deadline = time.monotonic() + timeout_seconds
        while not done_event.is_set() and time.monotonic() < deadline:
            if page is not None and not page.is_closed():
                page.wait_for_timeout(200)
            else:
                time.sleep(0.2)
        if not done_event.is_set():
            session["success"] = False

        if session["success"] and context is not None:
            save_state(platform, context.storage_state())
            set_state(platform, LOGGED_IN)
        else:
            set_state(platform, NOT_LOGGED_IN)
    finally:
        try:
            if browser is not None:
                browser.close()
            elif context is not None:
                context.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if pw is not None:
                pw.stop()
        except Exception:  # noqa: BLE001
            pass
        with _login_lock:
            _login_sessions.pop(platform, None)
        finished_event.set()


def complete_login(platform: str) -> bool:
    """Signal the login worker to save the storage state and close."""
    with _login_lock:
        entry = _login_sessions.get(platform)
    if entry is None:
        return False
    entry["session"]["success"] = True
    entry["done"].set()
    entry["finished"].wait(timeout=30)
    return True


def cancel_login(platform: str) -> bool:
    """Signal the login worker to close without saving."""
    with _login_lock:
        entry = _login_sessions.get(platform)
    if entry is None:
        return False
    entry["session"]["success"] = False
    entry["done"].set()
    entry["finished"].wait(timeout=30)
    return True


def fetch_search_html(platform: str, query: str) -> str:
    """Search with the saved login state and return the rendered HTML.

    Raises ``LoginRequiredError`` when no login state is saved, and
    ``LoginExpiredError`` (after marking the platform ``expired``) when the
    search lands on a verification page.
    """
    state = load_state(platform)
    if state is None:
        raise LoginRequiredError(platform)

    template = SEARCH_URL_TEMPLATES.get(platform)
    if template is None:
        raise LoginRequiredError(platform)
    url = template.format(query=quote(query))

    sync_playwright = _import_sync_playwright()

    persistent = platform in PERSISTENT_PLATFORMS
    user_dir = tempfile.mkdtemp(prefix="openlab-search-") if persistent else None
    with sync_playwright() as p:
        if persistent:
            # Baidu Xueshu must run in a non-incognito, HEADED persistent
            # context: headless triggers its anti-bot verification even with
            # valid login cookies. The browser window flashes briefly.
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_dir,
                headless=False,
                viewport={"width": 1366, "height": 768},
                locale="zh-CN",
            )
            context.add_init_script(_STEALTH_SCRIPT)
            context.add_cookies(state.get("cookies", []))
            page = context.pages[0] if context.pages else context.new_page()
        else:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                storage_state=state,
                user_agent=CHROME_UA,
                viewport={"width": 1366, "height": 768},
                locale="zh-CN",
            )
            context.add_init_script(_STEALTH_SCRIPT)
            page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)  # allow JS results to render
            if is_verification_page(page.url, page.title()):
                set_state(platform, EXPIRED)
                raise LoginExpiredError(platform)
            return page.content()
        finally:
            if persistent:
                context.close()
            else:
                browser.close()


def download_cnki_pdf(article_url: str, dest_path: str) -> None:
    """Download a CNKI paper PDF given its article detail-page URL.

    The article page embeds a signed ``#pdfDown`` link (``bar.cnki.net/bar/
    download/order?id=...``) that requires a valid login session and the
    article page as Referer. We open the article page with the saved login
    state, extract that link and fetch it inside the same browser context so
    cookies and Referer are correct.

    Raises ``LoginRequiredError`` / ``LoginExpiredError`` when the login state
    is missing or expired (the download redirects to ``login.cnki.net``), and
    ``RuntimeError`` when the download lands on the paywall page (``fee_*``) —
    the account lacks full-text download permission for that paper.
    """
    state = load_state("cnki")
    if state is None:
        raise LoginRequiredError("cnki")

    sync_playwright = _import_sync_playwright()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                storage_state=state,
                user_agent=CHROME_UA,
                viewport={"width": 1366, "height": 768},
                locale="zh-CN",
            )
            context.add_init_script(_STEALTH_SCRIPT)
            page = context.new_page()
            page.goto(article_url, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            if is_verification_page(page.url, page.title()):
                set_state("cnki", EXPIRED)
                raise LoginExpiredError("cnki")

            match = re.search(r'id="pdfDown"[^>]*href="([^"]+)"', page.content())
            if match is None:
                raise RuntimeError("知网文章页未找到 PDF 下载链接")

            download_url = match.group(1).replace("&amp;", "&")
            response = context.request.get(
                download_url, headers={"Referer": article_url}
            )
            if "login.cnki.net" in response.url or response.status >= 400:
                set_state("cnki", EXPIRED)
                raise LoginExpiredError("cnki")

            body = response.body()
            if body.startswith(b"%PDF"):
                Path(dest_path).write_bytes(body)
                return

            if "fee_" in response.url or "bar.cnki.net/bar/fee" in response.url:
                raise RuntimeError("该知网论文需要付费或机构订阅才能下载全文")

            raise RuntimeError("知网下载内容不是 PDF")
        finally:
            browser.close()
