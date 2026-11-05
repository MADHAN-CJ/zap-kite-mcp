# /markets

Analyse your connected Zerodha account and Indian market data in ChatGPT and Codex.
The `run_python` tool combines reads and calculations on the /markets server and
returns only the printed result. Intermediate candles, chains, and account rows can
stay on the server, keeping complex answers compact.

## Connect

1. Install /markets and connect its MCP server through OAuth.
2. Sign in to /markets using your email and the code delivered to your inbox.
3. Visit [the account app](https://app.slash.markets), sign in with that same email,
   and connect Zerodha. Renew that broker session each trading day.
4. Ask about your portfolio, market prices, indicators, or option chains. Ask explicitly
   to create an email watcher when you want scheduled notifications.

Never paste broker credentials or login codes into the conversation. Complete sign-in
on the relevant login page.

## Capabilities and boundaries

- Positions, holdings, funds, orders and trades are read-only broker data. No order
  placement, modification, or cancellation is available.
- Quotes, candles, instrument lookup, indicators, and derived option chains support
  Indian exchanges. Availability depends on market-data entitlements and session status.
- Computed option greeks and implied volatility are indicative. Analytics are not
  investment advice or a guarantee of future performance.
- Python can create, overwrite, or delete your persistent workspace files. This is
  separate from your brokerage account; deleted or overwritten files may not be recoverable.
- Scripts use a bounded Kite read gateway; arbitrary network access is unavailable.
- Watcher creation uses a separate tool and can send scheduled email alerts. The first
  check establishes a baseline; an already-true condition must become false and then
  true to alert. Use the returned management link to pause or cancel a watcher.

[Privacy](https://app.slash.markets/privacy) · [Terms](https://app.slash.markets/terms) ·
[Support](https://app.slash.markets/support)

Operated by Certus Innovations Private Limited. Not affiliated with Zerodha.
