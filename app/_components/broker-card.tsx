"use client";

import { Loader2Icon, PlugZapIcon, UnplugIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { type BrokerStatus, disconnectBroker, startKiteLogin } from "@/lib/client/api";
import { cn } from "@/lib/utils";

const LABEL: Record<BrokerStatus["status"], string> = {
  active: "Connected",
  token_expired: "Session expired",
  disconnected: "Disconnected",
  not_connected: "Not connected",
};

const STYLE: Record<BrokerStatus["status"], string> = {
  active: "bg-emerald-600/10 text-emerald-700",
  token_expired: "bg-red-600/10 text-red-700",
  disconnected: "bg-muted text-muted-foreground",
  not_connected: "bg-muted text-muted-foreground",
};

const fmt = (iso: string | null) =>
  iso
    ? new Date(iso).toLocaleString("en-IN", {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Asia/Kolkata",
      })
    : null;

export function BrokerCard({
  status,
  onChanged,
  onError,
}: {
  readonly status: BrokerStatus | null;
  readonly onChanged: (next: BrokerStatus) => void;
  readonly onError: (error: unknown) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const state = status?.status ?? "not_connected";
  const active = state === "active";

  const login = async () => {
    setBusy(true);
    try {
      window.location.assign(await startKiteLogin());
    } catch (e) {
      setBusy(false);
      onError(e);
    }
  };

  const disconnect = async () => {
    setConfirmOpen(false);
    setBusy(true);
    try {
      onChanged(await disconnectBroker());
    } catch (e) {
      onError(e);
    } finally {
      setBusy(false);
    }
  };

  const note = {
    active: `Kite sessions end around 06:00 IST; this one expires ${fmt(status?.expiresAt ?? null) ?? "tomorrow morning"}.`,
    token_expired:
      "Zerodha ended the daily session. Log in again to resume Claude access and watchers.",
    disconnected: "Log in to Zerodha to let Claude read this account.",
    not_connected: "Log in to Zerodha to let Claude read this account. Slash Markets never places orders.",
  }[state];

  return (
    <section className="flex flex-col gap-3 rounded-lg border bg-card p-4">
      <div className="flex items-center gap-2">
        <PlugZapIcon className="size-4 text-muted-foreground" />
        <span className="flex-1 font-medium">
          Zerodha
          {status?.kiteUserId ? (
            <span className="font-normal text-muted-foreground">
              {" "}
              · {status.kiteUserId}
              {status.userName ? ` (${status.userName})` : ""}
            </span>
          ) : null}
        </span>
        <span className={cn("rounded-full px-2 py-0.5 font-medium text-xs", STYLE[state])}>
          {status ? LABEL[state] : "…"}
        </span>
      </div>
      <p className="text-muted-foreground text-sm">{note}</p>
      <div className="flex items-center gap-2">
        <Button disabled={busy || !status} onClick={() => void login()} size="sm">
          {busy ? <Loader2Icon className="size-4 animate-spin" /> : null}
          {active ? "Log in again" : "Log in to Zerodha"}
        </Button>
        {active ? (
          <Button
            className="text-destructive hover:text-destructive"
            disabled={busy}
            onClick={() => setConfirmOpen(true)}
            size="sm"
            variant="ghost"
          >
            <UnplugIcon className="size-4" /> Disconnect
          </Button>
        ) : null}
      </div>

      <Dialog onOpenChange={setConfirmOpen} open={confirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Disconnect Zerodha</DialogTitle>
            <DialogDescription>
              Claude loses access and your watchers pause until you log in again.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2">
            <Button onClick={() => setConfirmOpen(false)} type="button" variant="ghost">
              Keep connected
            </Button>
            <Button
              className="text-destructive hover:text-destructive"
              onClick={() => void disconnect()}
              type="button"
              variant="ghost"
            >
              Disconnect
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}
