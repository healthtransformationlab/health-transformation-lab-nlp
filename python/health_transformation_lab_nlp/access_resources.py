"""The resources an AccessBench answer points to: its links and phone numbers, and whether each link opens (spec 043
US8, #935). The judge uses these to tell an exact, working resource from generic advice or an invented contact."""

from __future__ import annotations

import re
import socket
import urllib.error
import urllib.request
from typing import Callable

from .telemetry import traced

_LINK = re.compile(r"https?://[^\s<>\"'\]\)]+")
# a US number (optional +1, area code in brackets or not, any of - . space between groups) or a 3-digit service line
_PHONE = re.compile(r"(?<![\d$])(?:\+?1[\s.-]?)?\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-](\d{4})(?!\d)"
                    r"|(?<![\w$.-])(211|311|511|711|811|911|988)(?![\w-])")
_NO_HOST_ERRNOS = {-2, -3, -5, 8, 11001}            # getaddrinfo: the host doesn't exist (Linux, macOS, Windows)
_BLOCKED = {401, 403, 429}                           # the site refused a robot: unknown, not broken
UA = "AccessBench-link-check/1.0 (synthetic benchmark; one request per link)"


@traced
def extract_links(text: str) -> list[str]:
    """Each distinct http(s) link in the text, in order, without trailing punctuation."""
    out = []
    for m in _LINK.finditer(text or ""):
        url = m.group(0).rstrip(".,;:!?*_")
        if url not in out:
            out.append(url)
    return out


@traced
def extract_phones(text: str) -> list[str]:
    """Each distinct US phone number (as 800-555-0100) or 3-digit service line (211, 988, …), in order."""
    out = []
    for m in _PHONE.finditer(text or ""):
        num = "-".join(m.group(1, 2, 3)) if m.group(1) else m.group(4)
        if num not in out:
            out.append(num)
    return out


def _fetch(url: str, timeout: float = 8.0) -> int:
    """HTTP status for the link: HEAD first, GET when the site refuses HEAD. Raises on network errors."""
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 501):
                continue
            return e.code
    return 0


def _no_such_host(err: Exception) -> bool:
    reason = getattr(err, "reason", err)
    return isinstance(reason, socket.gaierror) or (isinstance(reason, OSError) and reason.errno in _NO_HOST_ERRNOS)


@traced
def check_links(urls: list[str], fetch: Callable[[str], int] | None = None) -> dict[str, bool | None]:
    """True for a link that opened (2xx/3xx), False for one that answered 4xx/5xx or whose host doesn't exist, None
    for one that couldn't be checked (a timeout, a refused robot, any other network error)."""
    fetch = fetch or _fetch
    out: dict[str, bool | None] = {}
    for url in urls:
        try:
            status = fetch(url)
        except Exception as e:  # noqa: BLE001 - a network failure is "unchecked", unless the host is gone
            out[url] = False if _no_such_host(e) else None
            continue
        out[url] = None if status in _BLOCKED or not status else status < 400
    return out
