# /markets

Ask Claude about your portfolio and the Indian markets. /markets connects Claude to your
broker account in read-only mode: it can analyse, it can never trade.

## What it does

- Positions, holdings, funds, today's orders and trades, mutual funds and GTTs from your
  broker account.
- Prices, market depth, intraday and daily candles for NSE and BSE stocks and indices, NFO and
  BFO futures and options, MCX commodities and CDS/BCD currency.
- Option chains with expiries, open interest, put-call ratio, max pain and computed Black-76
  implied volatility and greeks (indicative).
- Indicators such as EMA, RSI, MACD, Bollinger bands, ATR and VWAP.
- Watchers: Claude writes a condition, the /markets server checks it on a schedule during
  market hours and e-mails you when it becomes true. No AI tokens are spent on the checks.

## How to use it

1. Install the plugin and connect the bundled **/markets** connector from the plugin's
   Connectors tab. You sign in with your e-mail and a one-time code.
2. Open https://app.slash.markets, log in with the same e-mail, and connect your broker
   account. Broker sessions expire daily, so repeat this each trading day.
3. Ask Claude: "How is my portfolio doing?", "Is TCS bullish?", "What are NIFTY option writers
   positioned for this expiry?", "E-mail me when gold crosses 78,000."

Claude answers by writing a short Python script and running it on the /markets server through
the `run_python` tool. Only what the script prints comes back to Claude, so large data such as
candles and option chains never enters the conversation. The bundled skill teaches Claude the
library and the watcher contract.

## What data it sends and stores

- Scripts Claude writes are sent to `mcp.slash.markets` and run there with your broker
  session; the server keeps each script for up to 24 hours for diagnostics.
- Your broker access token is stored encrypted on the /markets server and never shown to
  Claude. Market data fetched by a script is returned to the conversation only as the script
  prints it and is not stored by /markets.
- Watchers store the condition, schedule and alert history so they can run without you.

Full details: [Privacy Policy](https://app.slash.markets/privacy) and
[Terms](https://app.slash.markets/terms). Source code: the `mcp/` folder of this repository.
/markets is operated by Certus Innovations Private Limited and is not affiliated with any
broker.
