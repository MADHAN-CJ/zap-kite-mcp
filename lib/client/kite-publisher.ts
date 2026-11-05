/**
 * Order form state for Zerodha's Kite Publisher button. /markets only pre-fills the order; the
 * user reviews and places it inside Kite's own window, so nothing here talks to our server.
 */

export const EXCHANGES = ["NSE", "BSE", "NFO", "BFO", "CDS", "MCX"] as const;
export const SIDES = ["BUY", "SELL"] as const;
export const PRODUCTS = ["CNC", "MIS", "NRML", "MTF"] as const;
export const ORDER_TYPES = ["MARKET", "LIMIT", "SL", "SL-M"] as const;

export type Exchange = (typeof EXCHANGES)[number];
export type Side = (typeof SIDES)[number];
export type Product = (typeof PRODUCTS)[number];
export type OrderType = (typeof ORDER_TYPES)[number];

export interface TradeForm {
  exchange: Exchange;
  tradingsymbol: string;
  side: Side;
  quantity: string;
  product: Product;
  orderType: OrderType;
  price: string;
  triggerPrice: string;
}

export const EMPTY_FORM: TradeForm = {
  exchange: "NSE",
  tradingsymbol: "",
  side: "BUY",
  quantity: "1",
  product: "CNC",
  orderType: "MARKET",
  price: "",
  triggerPrice: "",
};

export const needsPrice = (t: OrderType) => t === "LIMIT" || t === "SL";
export const needsTrigger = (t: OrderType) => t === "SL" || t === "SL-M";

const oneOf = <T extends string>(values: readonly T[], raw: string | null): T | null => {
  const v = raw?.trim().toUpperCase();
  return (values as readonly string[]).includes(v ?? "") ? (v as T) : null;
};

/** Reads a deep link such as `/?trade=1&exchange=NSE&tradingsymbol=INFY&side=BUY&quantity=5`. */
export function prefillFromParams(params: URLSearchParams): TradeForm | null {
  const raw = params.get("tradingsymbol") ?? "";
  if (!params.has("trade") && !raw.trim()) return null;
  const { exchange, tradingsymbol } = splitSymbol(
    raw,
    oneOf(EXCHANGES, params.get("exchange")) ?? EMPTY_FORM.exchange,
  );
  const orderType = oneOf(ORDER_TYPES, params.get("order_type")) ?? EMPTY_FORM.orderType;
  const num = (key: string) => {
    const v = params.get(key)?.trim() ?? "";
    return v && Number.isFinite(Number(v)) ? v : "";
  };
  return {
    exchange,
    tradingsymbol: tradingsymbol.slice(0, 40),
    side: oneOf(SIDES, params.get("side") ?? params.get("transaction_type")) ?? EMPTY_FORM.side,
    quantity: num("quantity") || EMPTY_FORM.quantity,
    product: oneOf(PRODUCTS, params.get("product")) ?? EMPTY_FORM.product,
    orderType,
    price: needsPrice(orderType) ? num("price") : "",
    triggerPrice: needsTrigger(orderType) ? num("trigger_price") : "",
  };
}

/** The exchange a watcher's market maps to; markets Kite does not trade on fall back to NSE. */
export function exchangeForMarket(market: string): Exchange {
  return oneOf(EXCHANGES, market) ?? "NSE";
}

/** Splits a Kite quote key such as `NSE:GOLDBEES`; a bare symbol takes the fallback exchange. */
export function splitSymbol(
  symbol: string,
  fallback: Exchange,
): { exchange: Exchange; tradingsymbol: string } {
  const [head, ...rest] = symbol.trim().toUpperCase().split(":");
  const exchange = rest.length > 0 ? oneOf(EXCHANGES, head ?? null) : null;
  return exchange
    ? { exchange, tradingsymbol: rest.join(":") }
    : { exchange: fallback, tradingsymbol: symbol.trim().toUpperCase() };
}

/** Builds the home-page deep link (path and query) that opens the card pre-filled. */
export function tradePath(form: Partial<TradeForm> & { tradingsymbol: string }): string {
  const url = new URL("/", "http://x");
  url.searchParams.set("trade", "1");
  url.searchParams.set("exchange", form.exchange ?? EMPTY_FORM.exchange);
  url.searchParams.set("tradingsymbol", form.tradingsymbol.toUpperCase());
  url.searchParams.set("side", form.side ?? EMPTY_FORM.side);
  url.searchParams.set("quantity", form.quantity ?? EMPTY_FORM.quantity);
  url.searchParams.set("product", form.product ?? EMPTY_FORM.product);
  url.searchParams.set("order_type", form.orderType ?? EMPTY_FORM.orderType);
  if (form.price) url.searchParams.set("price", form.price);
  if (form.triggerPrice) url.searchParams.set("trigger_price", form.triggerPrice);
  return `${url.pathname}${url.search}`;
}

export type Validated = { ok: true; entry: KitePublisherEntry } | { ok: false; error: string };

const positive = (raw: string, integer: boolean): number | null => {
  const n = Number(raw.trim());
  if (!raw.trim() || !Number.isFinite(n) || n <= 0) return null;
  return integer && !Number.isInteger(n) ? null : n;
};

/** Turns the form into a Publisher basket entry, or says what is missing. */
export function validate(form: TradeForm): Validated {
  const tradingsymbol = form.tradingsymbol.trim().toUpperCase();
  if (!tradingsymbol) return { ok: false, error: "Enter a trading symbol, e.g. INFY." };
  if (!/^[A-Z0-9&-]+$/.test(tradingsymbol)) {
    return { ok: false, error: "Trading symbols use letters, digits, & and - only." };
  }
  const quantity = positive(form.quantity, true);
  if (quantity === null) return { ok: false, error: "Quantity must be a whole number above 0." };
  const entry: KitePublisherEntry = {
    exchange: form.exchange,
    tradingsymbol,
    transaction_type: form.side,
    order_type: form.orderType,
    quantity,
    product: form.product,
  };
  if (needsPrice(form.orderType)) {
    const price = positive(form.price, false);
    if (price === null) return { ok: false, error: "Enter a limit price." };
    entry.price = price;
  }
  if (needsTrigger(form.orderType)) {
    const trigger = positive(form.triggerPrice, false);
    if (trigger === null) return { ok: false, error: "Enter a trigger price." };
    entry.trigger_price = trigger;
  }
  return { ok: true, entry };
}
