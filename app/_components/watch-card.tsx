"use client";

import { RadarIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { mutateWatch, type WatchAction, type WatchSummary } from "@/lib/client/api";
import { cn } from "@/lib/utils";

const STATUS_STYLE: Record<string, string> = {
  ARMED: "bg-emerald-600/10 text-emerald-700",
  PAUSED: "bg-amber-500/10 text-amber-700",
  ERROR: "bg-red-600/10 text-red-700",
  EXPIRED: "bg-muted text-muted-foreground",
  CANCELLED: "bg-muted text-muted-foreground",
};

const timeAgo = (iso: string | null): string | null => {
  if (!iso) return null;
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (mins < 48 * 60) return `${Math.round(mins / 60)}h ago`;
  return `${Math.round(mins / 1440)}d ago`;
};

const statusLabel = (w: WatchSummary): string => {
  if (w.status === "ARMED") return "watching";
  if (w.status === "PAUSED" && w.pausedBy === "broker") return "paused · session";
  return w.status.toLowerCase();
};

export function WatchCard({
  watch,
  onChanged,
}: {
  readonly watch: WatchSummary;
  readonly onChanged: (updated: WatchSummary) => void;
}) {
  const [busy, setBusy] = useState<WatchAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmCancelOpen, setConfirmCancelOpen] = useState(false);

  const act = async (action: WatchAction) => {
    setBusy(action);
    setError(null);
    try {
      onChanged(await mutateWatch(watch.id, action));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed.");
    } finally {
      setBusy(null);
    }
  };

  const live = watch.status === "ARMED" || watch.status === "PAUSED" || watch.status === "ERROR";
  const checked = timeAgo(watch.lastCheckedAt);
  const alerted = timeAgo(watch.lastAlertAt);
  const reason =
    watch.status === "ERROR" || watch.pausedBy === "broker" ? watch.statusReason : null;

  return (
    <div className="flex flex-col gap-2 rounded-lg border bg-card p-3 text-sm">
      <div className="flex items-center gap-2">
        <RadarIcon className="size-4 shrink-0 text-muted-foreground" />
        <span className="min-w-0 flex-1 truncate font-medium">
          {watch.symbol}{" "}
          <span className="font-normal text-muted-foreground">
            · {watch.market} · every {watch.checkEveryMinutes} min
          </span>
        </span>
        <span
          className={cn(
            "rounded-full px-2 py-0.5 font-medium text-xs",
            STATUS_STYLE[watch.status] ?? "bg-muted",
          )}
        >
          {statusLabel(watch)}
        </span>
      </div>
      <p className="text-muted-foreground">{watch.label}</p>
      {reason ? <p className="text-red-700 text-xs">{reason}</p> : null}
      <p className="text-muted-foreground/70 text-xs">
        {checked ? `checked ${checked}` : "not checked yet"}
        {watch.lastValue !== null ? ` · value ${watch.lastValue}` : ""}
        {watch.lastDetail ? ` · ${watch.lastDetail}` : ""}
        {alerted ? ` · alerted ${watch.alertCount}× (last ${alerted})` : ""}
        {` · expires ${new Date(watch.expiresAt).toLocaleDateString("en-IN", { day: "2-digit", month: "short" })}`}
      </p>
      {watch.recentAlerts.length > 0 ? (
        <ul className="text-muted-foreground text-xs">
          {watch.recentAlerts.map((a) => (
            <li key={a.at}>
              ⚡{" "}
              {new Date(a.at).toLocaleString("en-IN", {
                day: "2-digit",
                month: "short",
                hour: "2-digit",
                minute: "2-digit",
                timeZone: "Asia/Kolkata",
              })}
              {a.value !== null ? ` · ${a.value}` : ""}
            </li>
          ))}
        </ul>
      ) : null}
      {error ? <p className="text-red-700 text-xs">{error}</p> : null}
      {live ? (
        <div className="flex items-center gap-2">
          {watch.status === "ARMED" ? (
            <Button
              disabled={busy !== null}
              onClick={() => void act("pause")}
              size="xs"
              variant="secondary"
            >
              {busy === "pause" ? "Pausing…" : "Pause"}
            </Button>
          ) : (
            <Button
              disabled={busy !== null}
              onClick={() => void act("resume")}
              size="xs"
              variant="secondary"
            >
              {busy === "resume" ? "Resuming…" : "Resume"}
            </Button>
          )}
          <Button
            disabled={busy !== null}
            onClick={() => setConfirmCancelOpen(true)}
            size="xs"
            variant="ghost"
          >
            {busy === "cancel" ? "Cancelling…" : "Cancel"}
          </Button>
        </div>
      ) : null}

      <Dialog onOpenChange={setConfirmCancelOpen} open={confirmCancelOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel this watcher</DialogTitle>
            <DialogDescription>
              Stop watching {watch.symbol} ({watch.label})? A cancelled watcher cannot be restarted;
              ask Claude for a new one.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2">
            <Button onClick={() => setConfirmCancelOpen(false)} type="button" variant="ghost">
              Keep watching
            </Button>
            <Button
              className="text-destructive hover:text-destructive"
              onClick={() => {
                setConfirmCancelOpen(false);
                void act("cancel");
              }}
              type="button"
              variant="ghost"
            >
              Cancel watcher
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
