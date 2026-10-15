import { HttpError } from "./auth";
import { execute, one, query } from "./db";

export type WatchStatus = "ARMED" | "PAUSED" | "ERROR" | "EXPIRED" | "CANCELLED";
export type WatchAction = "pause" | "resume" | "cancel";

export interface WatchSummary {
  id: string;
  symbol: string;
  label: string;
  market: string;
  status: WatchStatus;
  statusReason: string | null;
  pausedBy: "user" | "broker" | null;
  checkEveryMinutes: number;
  lastCheckedAt: string | null;
  lastValue: string | null;
  lastDetail: string | null;
  lastError: string | null;
  alertCount: number;
  lastAlertAt: string | null;
  expiresAt: string;
  createdAt: string;
  recentAlerts: { at: string; value: string | null; detail: string | null }[];
}

interface WatchRow {
  id: string;
  symbol: string;
  label: string;
  market: string;
  status: WatchStatus;
  status_reason: string | null;
  paused_by: "user" | "broker" | null;
  check_every_s: number;
  last_checked_at: Date | null;
  last_value: string | null;
  last_detail: string | null;
  last_error: string | null;
  fired_count: number;
  last_fired_at: Date | null;
  expires_at: Date;
  created_at: Date;
}

interface FireRow {
  watcher_id: string;
  fired_at: Date;
  value: string | null;
  detail: string | null;
}

const iso = (d: Date | null): string | null => (d ? d.toISOString() : null);

export async function listWatches(userId: string): Promise<WatchSummary[]> {
  const rows = await query<WatchRow>(
    "SELECT * FROM watchers WHERE user_id = $1 ORDER BY created_at DESC",
    [userId],
  );
  if (rows.length === 0) return [];
  const fires = await query<FireRow>(
    "SELECT watcher_id, fired_at, value, detail FROM (" +
      "SELECT f.*, row_number() OVER (PARTITION BY watcher_id ORDER BY fired_at DESC) AS rn " +
      "FROM watcher_fires f WHERE watcher_id = ANY($1)) t WHERE rn <= 3 ORDER BY fired_at DESC",
    [rows.map((r) => r.id)],
  );
  return rows.map((r) => ({
    id: r.id,
    symbol: r.symbol,
    label: r.label,
    market: r.market,
    status: r.status,
    statusReason: r.status_reason,
    pausedBy: r.paused_by,
    checkEveryMinutes: Math.floor(r.check_every_s / 60),
    lastCheckedAt: iso(r.last_checked_at),
    lastValue: r.last_value,
    lastDetail: r.last_detail,
    lastError: r.last_error,
    alertCount: r.fired_count,
    lastAlertAt: iso(r.last_fired_at),
    expiresAt: r.expires_at.toISOString(),
    createdAt: r.created_at.toISOString(),
    recentAlerts: fires
      .filter((f) => f.watcher_id === r.id)
      .map((f) => ({ at: f.fired_at.toISOString(), value: f.value, detail: f.detail })),
  }));
}

export async function mutateWatch(
  userId: string,
  id: string,
  action: WatchAction,
): Promise<WatchSummary> {
  const row = await one<{ status: WatchStatus }>(
    "SELECT status FROM watchers WHERE id = $1 AND user_id = $2",
    [id, userId],
  );
  if (!row) throw new HttpError(404, "Watcher not found.");
  const { status } = row;
  if (action === "pause" && status === "ARMED") {
    await execute(
      "UPDATE watchers SET status = 'PAUSED', paused_by = 'user', status_reason = NULL, updated_at = now() WHERE id = $1",
      [id],
    );
  } else if (action === "resume" && (status === "PAUSED" || status === "ERROR")) {
    await execute(
      "UPDATE watchers SET status = 'ARMED', paused_by = NULL, status_reason = NULL, error_count = 0, " +
        "last_error = NULL, updated_at = now() WHERE id = $1",
      [id],
    );
  } else if (
    action === "cancel" &&
    (status === "ARMED" || status === "PAUSED" || status === "ERROR")
  ) {
    await execute(
      "UPDATE watchers SET status = 'CANCELLED', paused_by = NULL, updated_at = now() WHERE id = $1",
      [id],
    );
  } else {
    throw new HttpError(409, `Cannot ${action} a ${status.toLowerCase()} watcher.`);
  }
  const updated = (await listWatches(userId)).find((w) => w.id === id);
  if (!updated) throw new HttpError(404, "Watcher not found.");
  return updated;
}
