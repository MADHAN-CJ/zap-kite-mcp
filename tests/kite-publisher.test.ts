import { describe, expect, it } from "vitest";
import {
  EMPTY_FORM,
  exchangeForMarket,
  prefillFromParams,
  tradePath,
  validate,
} from "@/lib/client/kite-publisher";

describe("Kite Publisher order form", () => {
  it("validates a market order into a basket entry", () => {
    const res = validate({ ...EMPTY_FORM, tradingsymbol: " infy ", quantity: "5" });
    expect(res).toEqual({
      ok: true,
      entry: {
        exchange: "NSE",
        tradingsymbol: "INFY",
        transaction_type: "BUY",
        order_type: "MARKET",
        quantity: 5,
        product: "CNC",
      },
    });
  });

  it("requires price and trigger where the order type needs them", () => {
    const limit = validate({ ...EMPTY_FORM, tradingsymbol: "SBIN", orderType: "LIMIT" });
    expect(limit).toEqual({ ok: false, error: "Enter a limit price." });
    const sl = validate({
      ...EMPTY_FORM,
      tradingsymbol: "SBIN",
      orderType: "SL",
      price: "810.5",
      triggerPrice: "811",
    });
    expect(sl.ok && sl.entry.price === 810.5 && sl.entry.trigger_price === 811).toBe(true);
    const slm = validate({ ...EMPTY_FORM, tradingsymbol: "SBIN", orderType: "SL-M" });
    expect(slm).toEqual({ ok: false, error: "Enter a trigger price." });
  });

  it("rejects bad symbols and quantities", () => {
    expect(validate({ ...EMPTY_FORM }).ok).toBe(false);
    expect(validate({ ...EMPTY_FORM, tradingsymbol: "IN FY" }).ok).toBe(false);
    expect(validate({ ...EMPTY_FORM, tradingsymbol: "INFY", quantity: "0" }).ok).toBe(false);
    expect(validate({ ...EMPTY_FORM, tradingsymbol: "INFY", quantity: "1.5" }).ok).toBe(false);
    expect(validate({ ...EMPTY_FORM, tradingsymbol: "M&M", quantity: "2" }).ok).toBe(true);
  });

  it("round-trips a deep link through the prefill parser", () => {
    const link = tradePath({
      exchange: "NFO",
      tradingsymbol: "nifty25nov24700ce",
      side: "SELL",
      quantity: "75",
      product: "NRML",
      orderType: "LIMIT",
      price: "112.4",
    });
    expect(link.startsWith("/?trade=1&")).toBe(true);
    const form = prefillFromParams(new URL(link, "https://app.example").searchParams);
    expect(form).toEqual({
      exchange: "NFO",
      tradingsymbol: "NIFTY25NOV24700CE",
      side: "SELL",
      quantity: "75",
      product: "NRML",
      orderType: "LIMIT",
      price: "112.4",
      triggerPrice: "",
    });
  });

  it("maps watcher markets to a Kite exchange", () => {
    expect(exchangeForMarket("NFO")).toBe("NFO");
    expect(exchangeForMarket("mcx")).toBe("MCX");
    expect(exchangeForMarket("BCD")).toBe("NSE");
  });

  it("ignores unrelated query strings and falls back on bad values", () => {
    expect(prefillFromParams(new URLSearchParams("connected=1"))).toBeNull();
    const form = prefillFromParams(
      new URLSearchParams("trade=1&exchange=NYSE&side=HOLD&quantity=abc&order_type=LIMIT&price=x"),
    );
    expect(form).toEqual({ ...EMPTY_FORM, orderType: "LIMIT" });
  });
});
