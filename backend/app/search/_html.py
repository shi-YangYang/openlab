"""Minimal HTML link extraction for crawler search providers.

Search engines emit lots of navigational anchors (login, footer, pagination,
toolbar) that are not paper results. ``extract_links`` therefore filters
obvious noise and prefers anchors that sit inside result-like containers.
"""
import re
from html.parser import HTMLParser
from typing import List, Tuple

_RESULT_CLASS_TOKENS = (
    "result",
    "sc_content",
    "c-title",
    "title",
    "content",
    "item",
    "paper",
    "pub",
    "list-item",
    "search-result",
)

_NAV_TITLE_EXACT = {
    "登录",
    "注册",
    "首页",
    "帮助",
    "更多",
    "上一页",
    "下一页",
    "末页",
    "联系我们",
    "关于我们",
    "english",
    "退出",
    "设为首页",
    "加入收藏",
}

_NAV_HREF_FRAGMENTS = (
    "javascript",
    "login",
    "register",
    "passport",
    "about",
    "help",
    "wappass",
    "feedback",
    "mailto:",
)


def _is_result_class(class_attr: str) -> bool:
    for cls in re.split(r"\s+", class_attr or ""):
        lower = cls.lower()
        if any(token in lower for token in _RESULT_CLASS_TOKENS):
            return True
    return False


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: List[Tuple[str, str]] = []
        self._result_links: List[Tuple[str, str]] = []
        self._stack: List[Tuple[str, str]] = []
        self._a_href: str = ""
        self._a_text: List[str] = []
        self._a_in_result = False
        self._a_depth = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        if tag == "a":
            self._a_depth += 1
            self._a_href = ""
            self._a_text = []
            for key, value in attrs:
                if key == "href":
                    self._a_href = value or ""
            self._a_in_result = any(
                _is_result_class(cls) for _, cls in self._stack
            )
            return

        cls = ""
        for key, value in attrs:
            if key == "class":
                cls = value or ""
        self._stack.append((tag, cls))

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            text = "".join(self._a_text).strip()
            if text and self._a_href:
                entry = (text, self._a_href)
                if self._a_in_result:
                    self._result_links.append(entry)
                else:
                    self.links.append(entry)
            self._a_href = ""
            self._a_text = []
            self._a_depth = max(0, self._a_depth - 1)
            return

        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] == tag:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if self._a_depth > 0:
            self._a_text.append(data)


def _is_noise(title: str, href: str) -> bool:
    if len(title) <= 1 or title in _NAV_TITLE_EXACT:
        return True
    href_lower = (href or "").lower()
    if not href_lower.startswith(("http://", "https://")):
        return True
    if any(fragment in href_lower for fragment in _NAV_HREF_FRAGMENTS):
        return True
    return False


def extract_links(html: str) -> List[Tuple[str, str]]:
    """Return ``(anchor_text, href)`` pairs, result-container links first."""
    parser = _LinkParser()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 - HTML parsing must never crash search
        return []
    candidates = parser._result_links + parser.links
    return [(title, href) for title, href in candidates if not _is_noise(title, href)]
