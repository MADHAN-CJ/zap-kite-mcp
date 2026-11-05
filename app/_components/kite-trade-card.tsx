"use client";

import { ArrowRightLeftIcon, ChevronDownIcon } from "lucide-react";
import Script from "next/script";
import { useEffect, useId, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import {
  EMPTY_FORM,
  EXCHANGES,
  needsPrice,
  needsTrigger,
  ORDER_TYPES,
  PRODUCTS,
  SIDES,
  type TradeForm,
  validate,
} from "@/lib/client/kite-publisher";
import { cn } from "@/lib/utils";

const PUBLISHER_JS = "https://kite.trade/publisher.js?v=3";

const selectClass =
  "min-h-[50px] w-full appearance-none rounded-full border border-input bg-[#fffef9] py-0 pr-11 pl-5 text-base text-foreground outline-none transition-[border-color,box-shadow] duration-150 focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/25";

function Field({
  id,
  label,
  children,
  className,
}: {
  readonly id: string;
  readonly label: string;
  readonly children: React.ReactNode;
  readonly className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <label className="pl-3 text-muted-foreground text-sm" htmlFor={id}>
        {label}
      </label>
      {children}
    </div>
  );
}

function Select<T extends string>({
  id,
  value,
  options,
  onChange,
}: {
  readonly id: string;
  readonly value: T;
  readonly options: readonly T[];
  readonly onChange: (next: T) => void;
}) {
  return (
    <span className="relative block">
      <select
        className={selectClass}
        id={id}
        onChange={(e) => onChange(e.target.value as T)}
        value={value}
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
      <ChevronDownIcon className="pointer-events-none absolute top-1/2 right-4 size-4 -translate-y-1/2 text-muted-foreground" />
    </span>
  );
}

/**
 * Zerodha's Kite Publisher button. /markets pre-fills the order from this form; the user reviews,
 * edits and places it in Kite's own popup, signed in to Zerodha themselves. Nothing is sent to our
 * server, so /markets itself never places an order.
 */
export function KiteTradeCard({
  apiKey,
  prefill,
}: {
  readonly apiKey: string | null;
  readonly prefill: TradeForm | null;
}) {
  const [form, setForm] = useState<TradeForm>(prefill ?? EMPTY_FORM);
  const [ready, setReady] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const container = useRef<HTMLDivElement>(null);
  const section = useRef<HTMLElement>(null);
  const uid = useId().replace(/:/g, "");
  const buttonId = `kite-button-${uid}`;
  const fid = (name: string) => `${uid}-${name}`;
  const set = <K extends keyof TradeForm>(key: K, value: TradeForm[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const checked = validate(form);
  const entryKey = checked.ok ? JSON.stringify(checked.entry) : null;

  useEffect(() => {
    if (window.KiteConnect) setReady(true);
  }, []);

  useEffect(() => {
    if (!prefill) return;
    setForm(prefill);
    setResult(null);
    section.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [prefill]);

  useEffect(() => {
    const host = container.current;
    const sdk = window.KiteConnect;
    if (!ready || !sdk || !apiKey || !host || !entryKey) return;
    host.replaceChildren();
    sdk.ready(() => {
      if (container.current !== host) return;
      const kite = new sdk(apiKey);
      kite.add(JSON.parse(entryKey) as KitePublisherEntry);
      kite.finished((status) => {
        setResult(
          status === "success"
            ? "Kite reported the order as placed. Check the order book in Kite for the status."
            : `Kite closed without placing the order (${status}).`,
        );
      });
      kite.renderButton(`#${buttonId}`);
    });
    return () => host.replaceChildren();
  }, [ready, apiKey, entryKey, buttonId]);

  return (
    <section className="flex flex-col gap-3 rounded-2xl border bg-surface p-5" ref={section}>
      <Script onReady={() => setReady(true)} src={PUBLISHER_JS} strategy="afterInteractive" />
      <div className="flex items-center gap-2">
        <ArrowRightLeftIcon className="size-4 text-muted-foreground" />
        <span className="flex-1 font-medium text-lg">Trade on Kite</span>
      </div>
      <p className="text-muted-foreground">
        Pre-fill an order here, then place it yourself in Zerodha's Kite window. You log in to
        Zerodha in that window, can edit every field, and only you can submit it. /markets never
        sees or sends the order.
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field id={fid("exchange")} label="Exchange">
          <Select
            id={fid("exchange")}
            onChange={(v) => set("exchange", v)}
            options={EXCHANGES}
            value={form.exchange}
          />
        </Field>
        <Field className="col-span-2 sm:col-span-3" id={fid("symbol")} label="Trading symbol">
          <Input
            autoCapitalize="characters"
            id={fid("symbol")}
            onChange={(e) => set("tradingsymbol", e.target.value.toUpperCase())}
            placeholder="INFY"
            spellCheck={false}
            value={form.tradingsymbol}
          />
        </Field>
        <Field id={fid("side")} label="Side">
          <Select
            id={fid("side")}
            onChange={(v) => set("side", v)}
            options={SIDES}
            value={form.side}
          />
        </Field>
        <Field id={fid("quantity")} label="Quantity">
          <Input
            id={fid("quantity")}
            inputMode="numeric"
            min={1}
            onChange={(e) => set("quantity", e.target.value)}
            type="number"
            value={form.quantity}
          />
        </Field>
        <Field id={fid("product")} label="Product">
          <Select
            id={fid("product")}
            onChange={(v) => set("product", v)}
            options={PRODUCTS}
            value={form.product}
          />
        </Field>
        <Field id={fid("orderType")} label="Order type">
          <Select
            id={fid("orderType")}
            onChange={(v) => set("orderType", v)}
            options={ORDER_TYPES}
            value={form.orderType}
          />
        </Field>
        {needsPrice(form.orderType) ? (
          <Field className="col-span-2" id={fid("price")} label="Limit price">
            <Input
              id={fid("price")}
              inputMode="decimal"
              onChange={(e) => set("price", e.target.value)}
              step="0.05"
              type="number"
              value={form.price}
            />
          </Field>
        ) : null}
        {needsTrigger(form.orderType) ? (
          <Field className="col-span-2" id={fid("trigger")} label="Trigger price">
            <Input
              id={fid("trigger")}
              inputMode="decimal"
              onChange={(e) => set("triggerPrice", e.target.value)}
              step="0.05"
              type="number"
              value={form.triggerPrice}
            />
          </Field>
        ) : null}
      </div>

      <div className="flex min-h-12 flex-wrap items-center gap-3">
        {!apiKey ? (
          <p className="text-muted-foreground text-sm">Kite Publisher is not configured.</p>
        ) : !checked.ok ? (
          <p className="text-muted-foreground text-sm">{checked.error}</p>
        ) : !ready ? (
          <p className="text-muted-foreground text-sm">Loading the Kite button…</p>
        ) : null}
        <div id={buttonId} ref={container} />
      </div>
      {result ? <p className="rounded-xl bg-surface px-4 py-2 text-sm">{result}</p> : null}
      <p className="text-muted-foreground text-sm">
        Orders are placed on Zerodha, under Zerodha's terms and brokerage. The Kite window may not
        open inside some in-app browsers; use Safari or Chrome if nothing appears.
      </p>
    </section>
  );
}
