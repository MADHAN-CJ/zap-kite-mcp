from __future__ import annotations

import html

_SHELL = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>{title} · Slash Markets</title>
<style>
  :root {{ color-scheme: light dark; --brand: #0c6b3d; --danger: #b3261e; }}
  body {{ font: 15px/1.5 system-ui, sans-serif; max-width: 44rem; margin: 6vh auto; padding: 0 16px; }}
  h1 {{ font-size: 1.15rem; margin-bottom: .25rem; }}
  h2 {{ font-size: 1rem; margin-top: 1.8rem; }}
  .brand {{ display: inline-block; background: var(--brand); color: #fff; border-radius: 8px;
           padding: 4px 10px; font-weight: 700; text-decoration: none; }}
  .meta {{ color: #888; font-size: .85rem; }}
  .card {{ border: 1px solid #8884; border-radius: 10px; padding: 14px 16px; margin: 12px 0; }}
  .row {{ display: flex; justify-content: space-between; gap: 8px; align-items: baseline; flex-wrap: wrap; }}
  .chip {{ font-size: .75rem; font-weight: 700; border-radius: 999px; padding: 2px 10px; }}
  .c-ARMED, .c-active {{ background: #0c6b3d22; color: var(--brand); }}
  .c-PAUSED {{ background: #8886; }}
  .c-ERROR, .c-token_expired {{ background: #b3261e22; color: var(--danger); }}
  .c-EXPIRED, .c-CANCELLED, .c-disconnected, .c-not_connected {{ background: #8883; color: #888; }}
  .err {{ background: #b3261e22; border: 1px solid var(--danger); border-radius: 6px; padding: .6rem .8rem; }}
  .ok {{ background: #0c6b3d22; border: 1px solid var(--brand); border-radius: 6px; padding: .6rem .8rem; }}
  form.inline {{ display: inline; }}
  button {{ padding: .4rem 1rem; font: inherit; border: 1px solid #8886; border-radius: 6px;
           background: transparent; cursor: pointer; }}
  button.primary {{ background: var(--brand); border: 0; color: #fff; }}
  button.danger {{ color: var(--danger); border-color: #b3261e66; }}
  label {{ display: block; margin: 1rem 0 .25rem; font-weight: 600; }}
  input {{ width: 100%; box-sizing: border-box; padding: .55rem; font: inherit;
          border: 1px solid #8888; border-radius: 6px; }}
  .fires {{ font-size: .82rem; color: #888; margin-top: 6px; }}
  .actions {{ margin-top: 10px; }}
  code {{ font-size: .9em; }}
</style></head><body>
<p><a class="brand" href="{home}">&#9889; Slash Markets</a></p>
{body}
</body></html>"""


def shell(title: str, body: str, home: str) -> str:
    return _SHELL.format(title=html.escape(title), body=body, home=html.escape(home))


def error_box(message: str) -> str:
    return f'<p class="err">{html.escape(message)}</p>'


def email_form(action: str, title: str, sub: str, notice: str = "", hidden: str = "") -> str:
    return (
        f"<h1>{html.escape(title)}</h1><p class='meta'>{html.escape(sub)}</p>{notice}"
        f'<form method="post" action="{html.escape(action)}">{hidden}'
        '<label for="email">Email</label>'
        '<input id="email" name="email" type="email" autocomplete="email" autofocus required>'
        '<button class="primary" style="margin-top:1.2rem" type="submit">Send code</button></form>'
    )


def otp_form(action: str, email: str, notice: str = "", hidden: str = "") -> str:
    return (
        "<h1>Enter your login code</h1>"
        f"<p class='meta'>Sent to {html.escape(email)}. It expires in 10 minutes.</p>{notice}"
        f'<form method="post" action="{html.escape(action)}">{hidden}'
        f'<input type="hidden" name="email" value="{html.escape(email)}">'
        '<label for="code">6-digit code</label>'
        '<input id="code" name="code" inputmode="numeric" pattern="[0-9]*" '
        'autocomplete="one-time-code" autofocus required>'
        '<button class="primary" style="margin-top:1.2rem" type="submit">Sign in</button></form>'
    )


def hidden(name: str, value: str) -> str:
    return f'<input type="hidden" name="{html.escape(name)}" value="{html.escape(value)}">'
