/** Globals installed by https://kite.trade/publisher.js?v=3 (Zerodha's Kite Publisher plugin). */

interface KitePublisherEntry {
  exchange: string;
  tradingsymbol: string;
  transaction_type: "BUY" | "SELL";
  order_type: "MARKET" | "LIMIT" | "SL" | "SL-M";
  quantity: number;
  product?: "CNC" | "MIS" | "NRML" | "MTF";
  price?: number;
  trigger_price?: number;
  disclosed_quantity?: number;
  validity?: "DAY" | "IOC";
  variety?: "regular" | "amo" | "co" | "iceberg" | "auction";
  readonly?: boolean;
  tag?: string;
}

interface KitePublisher {
  add(entry: KitePublisherEntry): void;
  get(): KitePublisherEntry[];
  count(): number;
  renderButton(selector: string): void;
  link(selector: string): void;
  finished(callback: (status: string, requestToken?: string) => void): void;
  setOption(key: "redirect_url", value: string): void;
}

interface KitePublisherStatic {
  new (apiKey: string): KitePublisher;
  ready(callback: () => void): void;
}

declare var KiteConnect: KitePublisherStatic | undefined;
