from __future__ import annotations

import html
from urllib.parse import quote

_SHELL = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>{title} · /markets</title>
<style>
  :root {{ color-scheme: light; --ink: #20251b; --muted: #62675f; --surface: #f7f6f2; --border: #e4e7dc;
          --select: #f6d64d; --button: #171a17; --negative: #a43c2f; --negative-surface: #f8e3df;
          --positive: #34432e; --positive-surface: #e6efdc; --ring: #4a6640; }}
  body {{ margin: 0; background: #fff; color: var(--ink); font: 16px/1.6 "Onest", Arial, sans-serif;
         -webkit-font-smoothing: antialiased; }}
  main {{ max-width: 28rem; margin: 10vh auto; padding: 0 20px; }}
  h1 {{ font-family: "Libre Baskerville", Georgia, serif; font-weight: 500; font-size: 1.75rem;
       line-height: 1.2; letter-spacing: -.025em; margin: 1.4rem 0 .4rem; text-wrap: pretty; }}
  .brand {{ display: inline-flex; align-items: center; gap: 8px; color: var(--ink); text-decoration: none;
           font-weight: 500; font-size: 1.1rem; }}
  .brand svg {{ height: 26px; width: auto; }}
  .slash {{ display: inline-block; width: .424em; height: .8em; margin-right: .04em; vertical-align: -.12em;
           overflow: hidden; text-indent: 1em; background: currentColor;
           mask: url("data:image/svg+xml,{slash}") center / contain no-repeat;
           -webkit-mask: url("data:image/svg+xml,{slash}") center / contain no-repeat; }}
  .meta {{ color: var(--muted); }}
  .err {{ background: var(--negative-surface); color: var(--negative); border-radius: 12px; padding: .7rem 1rem; }}
  .ok {{ background: var(--positive-surface); color: var(--positive); border-radius: 12px; padding: .7rem 1rem; }}
  label {{ display: block; margin: 1.2rem 0 .4rem; font-weight: 500; }}
  input {{ width: 100%; box-sizing: border-box; min-height: 50px; padding: 0 20px; font: inherit;
          color: var(--ink); background: #fffef9; border: 1px solid var(--border); border-radius: 999px; }}
  input:focus-visible {{ outline: 2px solid var(--ring); outline-offset: 3px; }}
  button {{ display: inline-flex; align-items: center; justify-content: center; min-height: 50px; padding: 0 21px;
           margin-top: 1.2rem; font: inherit; color: #fff; background: var(--button); border: 1px solid var(--button);
           border-radius: 999px; cursor: pointer; transition: background 160ms ease; }}
  button:hover {{ background: #343a32; }}
  button:focus-visible {{ outline: 2px solid var(--ring); outline-offset: 4px; }}
</style></head><body><main>
<a class="brand" href="{home}">{logomark}<span><span class="slash" aria-hidden="true">/</span>markets</span></a>
{body}
</main></body></html>"""

_LOGOMARK = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 341 174" fill="#34432e" aria-hidden="true">'
    "{paths}</svg>"
)


LOGOMARK_PATHS = '<path d="M321.7 103.317V95.0774H299.058V63.705H288.6V53.5602H278.915V43.7356H258.948V35.0202H201.585V43.4187H183.203V53.5602H173.376V63.2264H156.227V56.0956H136.299V27.5724H129.009V17.7478H120.452V8.55696H106.191V0H55.4829V8.55696H37.5767V17.7478H28.5602V28.0478H0.338053C-0.422566 27.2872 0.338053 51.9756 0.338053 51.9756H19.6704V86.2035H27.5936V102.684H36.4674V112.508H45.9752V121.382H55.4829V128.671H67.843V155.927H75.9246V164.801H83.3723V173.358H129.009V164.484H139.468V154.659H149.926V136.404H134.08V144.835H120.136V155.61H92.0116V147.37H83.3723V130.89H91.6123V121.382H99.2185V112.508H107.554V102.684H116.016V93.3343H122.671V85.8897H129.957V78.1219H146.757V85.6932H155.631V127.486H165.931V144.835H174.647V155.61H184.947V164.801H193.979V173.358H266.555V165.2H277.013V154.659H287.155V144.518H296.979V122.967H308.23V128.671H340.398V103.317H321.7ZM119.343 75.428H110.945V84.6188H101.754V93.8097H92.2462V103.317H83.3723V112.825H61.8214V107.247H53.5814V97.318H44.0736V83.6681H37.5767V33.9109H46.926V25.354H56.7506V16.797H98.7431V26.3047H109.994V34.8617H119.343V75.428ZM281.767 130.89H274.164V140.081H264.97V149.905H253.779V159.571H204.913V149.905H193.098V140.081H182.887V124.551H174.013V77.6465H183.203V69.0895H193.028V59.7403H202.853V52.1341H249.124V61.4834H262.752V71.308H272.735V81.7665H281.767V130.89Z"/><path d="M201.582 81.9258H229.696V90.6412H241.85V115.995H236.761V124.552H220.281V115.995H210.773V90.9581H201.582V81.9258Z"/><path d="M53.4961 41.8828H81.6073V50.5982H93.7614V75.9522H88.6747V84.5092H72.1946V75.9522H62.6869V50.9152H53.4961V41.8828Z"/>'
_SLASH_DATA = quote(
    '<svg width="60" height="113" viewBox="0 0 60 113" fill="none" xmlns="http://www.w3.org/2000/svg">\n<path d="M39.5479 80.2607H19.7744V112.829H0V80.2598H19.7734V32.5703H39.5479V80.2607ZM59.3213 32.5693H39.5469V0H59.3213V32.5693Z" fill="black"/>\n</svg>',
    safe="",
)


def shell(title: str, body: str, home: str) -> str:
    return _SHELL.format(
        title=html.escape(title),
        body=body,
        home=html.escape(home),
        logomark=_LOGOMARK.format(paths=LOGOMARK_PATHS),
        slash=_SLASH_DATA,
    )


def error_box(message: str) -> str:
    return f'<p class="err">{html.escape(message)}</p>'


def email_form(action: str, title: str, sub: str, notice: str = "", hidden: str = "") -> str:
    return (
        f"<h1>{html.escape(title)}</h1><p class='meta'>{html.escape(sub)}</p>{notice}"
        f'<form method="post" action="{html.escape(action)}">{hidden}'
        '<label for="email">Email</label>'
        '<input id="email" name="email" type="email" autocomplete="email" autofocus required>'
        '<button type="submit">Send code</button></form>'
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
        '<button type="submit">Sign in</button></form>'
    )


def hidden(name: str, value: str) -> str:
    return f'<input type="hidden" name="{html.escape(name)}" value="{html.escape(value)}">'
