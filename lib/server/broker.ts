import { decrypt, encrypt } from "./crypto";
import { execute, one } from "./db";
import { invalidateSession, type KiteSession, nextTokenExpiry } from "./kite";

export type BrokerStatusValue = "active" | "token_expired" | "disconnected" | "not_connected";

export interface BrokerStatus {
  status: BrokerStatusValue;
  kiteUserId: string | null;
  userName: string | null;
  connectedAt: string | null;
  expiresAt: string | null;
}

interface Row {
  status: BrokerStatusValue;
  kite_user_id: string;
  user_name: string | null;
  access_token_enc: string | null;
  connected_at: Date;
  expires_at: Date | null;
}

export async function brokerStatus(userId: string): Promise<BrokerStatus> {
  const row = await one<Row>(
    "SELECT status, kite_user_id, user_name, connected_at, expires_at FROM broker_connections WHERE user_id = $1",
    [userId],
  );
  if (!row) {
    return {
      status: "not_connected",
      kiteUserId: null,
      userName: null,
      connectedAt: null,
      expiresAt: null,
    };
  }
  return {
    status: row.status,
    kiteUserId: row.kite_user_id,
    userName: row.user_name,
    connectedAt: row.connected_at.toISOString(),
    expiresAt: row.expires_at?.toISOString() ?? null,
  };
}

export async function storeSession(userId: string, session: KiteSession): Promise<void> {
  await execute(
    "INSERT INTO broker_connections (user_id, kite_user_id, user_name, access_token_enc, status, " +
      "connected_at, expires_at, updated_at) VALUES ($1, $2, $3, $4, 'active', now(), $5, now()) " +
      "ON CONFLICT (user_id) DO UPDATE SET kite_user_id = excluded.kite_user_id, " +
      "user_name = excluded.user_name, access_token_enc = excluded.access_token_enc, " +
      "status = 'active', connected_at = now(), expires_at = excluded.expires_at, " +
      "token_mail_sent_on = NULL, updated_at = now()",
    [userId, session.userId, session.userName, encrypt(session.accessToken), nextTokenExpiry()],
  );
  await execute(
    "UPDATE watchers SET status = 'ARMED', paused_by = NULL, status_reason = NULL, error_count = 0, " +
      "updated_at = now() WHERE user_id = $1 AND status = 'PAUSED' AND paused_by = 'broker' " +
      "AND expires_at > now()",
    [userId],
  );
}

export async function disconnect(userId: string): Promise<void> {
  const row = await one<Pick<Row, "status" | "access_token_enc">>(
    "SELECT status, access_token_enc FROM broker_connections WHERE user_id = $1",
    [userId],
  );
  if (row?.status === "active" && row.access_token_enc) {
    await invalidateSession(decrypt(row.access_token_enc));
  }
  await execute(
    "UPDATE broker_connections SET status = 'disconnected', access_token_enc = NULL, updated_at = now() " +
      "WHERE user_id = $1",
    [userId],
  );
  await execute(
    "UPDATE watchers SET status = 'PAUSED', paused_by = 'broker', status_reason = $2, updated_at = now() " +
      "WHERE user_id = $1 AND status = 'ARMED'",
    [userId, "Zerodha is disconnected. Log in again in the Zap app, then resume."],
  );
}
