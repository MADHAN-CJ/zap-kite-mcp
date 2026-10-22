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
  active: "bg-positive-surface text-positive",
  token_expired: "bg-negative-surface text-negative",
  disconnected: "bg-surface text-muted-foreground",
  not_connected: "bg-surface text-muted-foreground",
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
    active: `Zerodha ends every session during its overnight reset, usually between 05:30 and 07:30 IST. This one likely ends by ${fmt(status?.expiresAt ?? null) ?? "tomorrow morning"}.`,
    token_expired:
      "Zerodha ended the daily session. Log in again to resume Claude access and watchers.",
    disconnected: "Log in to Zerodha to let Claude read this account.",
    not_connected:
      "Log in to Zerodha to let Claude read this account. /markets never places orders.",
  }[state];

  return (
    <section className="flex flex-col gap-3 rounded-2xl border bg-surface p-5">
      <div className="flex items-center gap-2">
        <PlugZapIcon className="size-4 text-muted-foreground" />
        <span className="flex-1 font-medium text-lg">
          Zerodha
          {status?.kiteUserId ? (
            <span className="font-normal text-muted-foreground">
              {" "}
              · {status.kiteUserId}
              {status.userName ? ` (${status.userName})` : ""}
            </span>
          ) : null}
        </span>
        <span className={cn("rounded-full px-3 py-1 font-medium text-sm", STYLE[state])}>
          {status ? LABEL[state] : "…"}
        </span>
      </div>
      <p className="text-muted-foreground">{note}</p>
      <div className="flex flex-wrap items-center gap-2">
        <Button disabled={busy || !status} onClick={() => void login()}>
          {busy ? <Loader2Icon className="size-4 animate-spin" /> : null}
          {active ? "Log in again" : "Log in to Zerodha"}
        </Button>
        {active ? (
          <Button disabled={busy} onClick={() => setConfirmOpen(true)} variant="destructive">
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
            <Button onClick={() => setConfirmOpen(false)} size="sm" type="button" variant="ghost">
              Keep connected
            </Button>
            <Button onClick={() => void disconnect()} size="sm" type="button" variant="destructive">
              Disconnect
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}
