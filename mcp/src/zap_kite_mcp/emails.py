"""Transactional emails in the /markets brand: HTML with a plain-text twin for every message."""

from __future__ import annotations

import html
from dataclasses import dataclass

INK = "#20251b"
MUTED = "#62675f"
SURFACE = "#f7f6f2"
BORDER = "#e4e7dc"
SELECT = "#f6d64d"
BUTTON = "#171a17"
SERIF = "'Libre Baskerville', Georgia, 'Times New Roman', serif"
SANS = "Onest, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif"
MONO = "'Departure Mono', ui-monospace, Menlo, Consolas, monospace"

LOGOMARK_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="62" height="32" viewBox="0 0 341 174" '
    'fill="#34432e" role="img" aria-label="/markets">{paths}</svg>'
)


@dataclass(frozen=True)
class Email:
    subject: str
    html: str
    text: str


def _wordmark() -> str:
    return (
        f'<span style="font-family:{SANS};font-size:18px;font-weight:600;color:{INK};'
        'letter-spacing:-.01em">/markets</span>'
    )


def _button(label: str, href: str) -> str:
    return (
        f'<a href="{html.escape(href)}" style="display:inline-block;min-height:48px;line-height:48px;'
        f"padding:0 24px;border-radius:999px;background:{BUTTON};color:#ffffff;font-family:{SANS};"
        f'font-size:16px;text-decoration:none">{html.escape(label)}</a>'
    )


def _shell(preheader: str, headline: str, body: str, footer: str, logomark_paths: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta name="color-scheme" content="light"><title>{html.escape(headline)}</title></head>
<body style="margin:0;padding:0;background:#ffffff;color:{INK}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">{html.escape(preheader)}</div>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#ffffff">
<tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:520px">
<tr><td style="padding:0 0 28px">
  <table role="presentation" cellspacing="0" cellpadding="0"><tr>
    <td style="padding-right:10px;vertical-align:middle">{LOGOMARK_SVG.format(paths=logomark_paths)}</td>
    <td style="vertical-align:middle">{_wordmark()}</td>
  </tr></table>
</td></tr>
<tr><td style="padding:0 0 12px;font-family:{SERIF};font-size:30px;line-height:1.2;font-weight:500;letter-spacing:-.02em;color:{INK}">{headline}</td></tr>
<tr><td style="font-family:{SANS};font-size:16px;line-height:1.65;color:{INK}">{body}</td></tr>
<tr><td style="padding:32px 0 0;border-top:1px solid {BORDER};margin-top:32px;font-family:{SANS};font-size:13px;line-height:1.6;color:{MUTED}">{footer}</td></tr>
</table></td></tr></table></body></html>"""


def _p(text: str) -> str:
    return f'<p style="margin:0 0 16px">{text}</p>'


def _muted(text: str) -> str:
    return f'<p style="margin:0 0 16px;color:{MUTED}">{text}</p>'


def login_code(code: str, logomark_paths: str = "") -> Email:
    code_html = (
        f'<div style="margin:8px 0 24px;padding:20px 24px;border-radius:14px;background:{SURFACE};'
        f"font-family:{MONO};font-size:34px;letter-spacing:.32em;color:{INK};text-align:center"
        f'">{html.escape(code)}</div>'
    )
    body = (
        _p("Enter this code to sign in. It expires in 10 minutes.")
        + code_html
        + _muted(
            "If you didn't request it, ignore this email. Nobody can use the code without your inbox."
        )
    )
    footer = "/markets is read-only. It can never place, change or cancel an order."
    return Email(
        subject=f"{code} is your /markets login code",
        html=_shell(f"Your login code is {code}", "Your login code", body, footer, logomark_paths),
        text=(
            f"Your /markets login code is {code}. It expires in 10 minutes.\n\n"
            "If you didn't request it, ignore this email.\n\n"
            "/markets is read-only. It can never place, change or cancel an order."
        ),
    )


def watcher_alert(
    symbol: str,
    label: str,
    value: str | None,
    detail: str | None,
    when: str,
    page_url: str,
    logomark_paths: str = "",
) -> Email:
    rows = [("Condition", label)]
    if value is not None:
        rows.append(("Value", value))
    if detail:
        rows.append(("Detail", detail))
    rows.append(("Time", when))
    table = "".join(
        f'<tr><td style="padding:6px 12px 6px 0;color:{MUTED};white-space:nowrap;vertical-align:top">'
        f'{html.escape(k)}</td><td style="padding:6px 0;font-family:{MONO if k == "Value" else SANS}">'
        f"{html.escape(v)}</td></tr>"
        for k, v in rows
    )
    body = (
        _p(
            f'<span style="display:inline-block;padding:2px 8px;border-radius:6px;background:{SELECT}">'
            f"{html.escape(symbol)}</span> crossed the line you asked your AI to watch."
        )
        + f'<table role="presentation" cellspacing="0" cellpadding="0" style="margin:0 0 24px;font-size:16px">{table}</table>'
        + _p(_button("Manage watchers", page_url))
    )
    footer = (
        "/markets is read-only; it can never trade. "
        "This watcher alerts again only after the condition resets."
    )
    text_rows = "\n".join(f"{k}: {v}" for k, v in rows)
    return Email(
        subject=f"⚡ {symbol}: {label}",
        html=_shell(
            f"{symbol}: {label}",
            f"{html.escape(symbol)} just triggered.",
            body,
            footer,
            logomark_paths,
        ),
        text=(
            f"Your watcher on {symbol} just triggered.\n\n{text_rows}\n\n"
            f"Manage your watchers: {page_url}\n\n{footer}"
        ),
    )


def session_paused(page_url: str, logomark_paths: str = "") -> Email:
    body = (
        _p(
            "Zerodha ends every session during its overnight reset, so your /markets watchers "
            "are paused and your AI assistant can't read your account until you log in again."
        )
        + _p(_button("Log in to Zerodha", page_url))
        + _muted("Watchers resume by themselves after you log in. Nothing else to do.")
    )
    footer = "/markets is read-only; it can never trade."
    return Email(
        subject="/markets watchers paused: log in to Zerodha again",
        html=_shell(
            "Your Zerodha session ended; watchers are paused",
            "Log in to Zerodha again.",
            body,
            footer,
            logomark_paths,
        ),
        text=(
            "Your Zerodha session has ended (Kite sessions expire every morning), so your "
            "/markets watchers are paused.\n\nLog in to Zerodha again and they resume "
            f"automatically:\n{page_url}\n\n{footer}"
        ),
    )
