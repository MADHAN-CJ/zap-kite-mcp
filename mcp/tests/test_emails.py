from __future__ import annotations

from zap_kite_mcp.emails import login_code, session_paused, watcher_alert
from zap_kite_mcp.pages import LOGOMARK_PATHS

BRAND = ("#20251b", "#62675f", "#e4e7dc", "Libre Baskerville", "/markets")


def _assert_branded(html: str) -> None:
    for token in BRAND:
        assert token in html
    assert "<svg" in html and 'viewBox="0 0 341 174"' in html
    assert "Zap" not in html and "Slash Markets" not in html


def test_login_code_email() -> None:
    m = login_code("482913", LOGOMARK_PATHS)
    assert m.subject == "482913 is your /markets login code"
    _assert_branded(m.html)
    assert "482913" in m.html and "10 minutes" in m.html and "#f7f6f2" in m.html
    assert "482913" in m.text and "10 minutes" in m.text and "<" not in m.text


def test_watcher_alert_email() -> None:
    m = watcher_alert(
        "NIFTY",
        "RSI under 30",
        "28.9",
        "15m RSI14",
        "22 Oct 2026, 11:30 IST",
        "https://app",
        LOGOMARK_PATHS,
    )
    assert m.subject == "⚡ NIFTY: RSI under 30"
    _assert_branded(m.html)
    for piece in (
        "NIFTY",
        "RSI under 30",
        "28.9",
        "15m RSI14",
        "11:30 IST",
        'href="https://app"',
        "Manage watchers",
    ):
        assert piece in m.html
    assert "Value: 28.9" in m.text and "https://app" in m.text
    m2 = watcher_alert("GOLD", "above 78500", None, None, "x", "https://app")
    assert "Value" not in m2.text and "Detail" not in m2.text


def test_session_paused_email() -> None:
    m = session_paused("https://app/login", LOGOMARK_PATHS)
    assert m.subject.startswith("/markets watchers paused")
    _assert_branded(m.html)
    assert (
        'href="https://app/login"' in m.html
        and "resume by themselves" in m.html
        and "#171a17" in m.html
    )
    assert "https://app/login" in m.text


def test_escapes_user_content() -> None:
    m = watcher_alert("<b>X</b>", "a & b", None, None, "t", "https://app")
    assert "&lt;b&gt;X&lt;/b&gt;" in m.html and "a &amp; b" in m.html and "<b>X</b>" not in m.html
