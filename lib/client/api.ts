import type { BrokerStatus } from "@/lib/server/broker";
import type { WatchAction, WatchSummary } from "@/lib/server/watches";
import { authHeaders, type SessionUser, setSession } from "./session";

export type { BrokerStatus, WatchAction, WatchSummary };

export class SessionExpiredError extends Error {}

type Result<T> = { ok: true; value: T } | { ok: false; error: string };

async function failure(res: Response, fallback: string): Promise<Error> {
  if (res.status === 401) return new SessionExpiredError("Your session expired. Sign in again.");
  const body = (await res.json().catch(() => null)) as { error?: string } | null;
  return new Error(body?.error ?? fallback);
}

async function post<T>(path: string, body: unknown, fallback: string): Promise<Result<T>> {
  try {
    const res = await fetch(path, {
      method: "POST",
      headers: { ...authHeaders(), "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) return { ok: false, error: (await failure(res, fallback)).message };
    return { ok: true, value: (await res.json()) as T };
  } catch {
    return { ok: false, error: "Couldn't reach the server." };
  }
}

export async function requestOtp(email: string): Promise<Result<{ ok: true }>> {
  return post("/api/auth/request-otp", { email }, "Could not send the code.");
}

export async function verifyOtp(email: string, code: string): Promise<Result<SessionUser>> {
  const res = await post<{ token: string; user: SessionUser }>(
    "/api/auth/verify-otp",
    { email, code },
    "Invalid or expired code.",
  );
  if (!res.ok) return res;
  setSession(res.value.token, res.value.user);
  return { ok: true, value: res.value.user };
}

export async function getBrokerStatus(): Promise<BrokerStatus> {
  const res = await fetch("/api/broker", { headers: authHeaders() });
  if (!res.ok) throw await failure(res, "Could not load the Zerodha status.");
  return (await res.json()) as BrokerStatus;
}

export async function startKiteLogin(): Promise<string> {
  const res = await fetch("/api/broker/kite/login/start", {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw await failure(res, "Could not start the Zerodha login.");
  return ((await res.json()) as { loginUrl: string }).loginUrl;
}

export async function disconnectBroker(): Promise<BrokerStatus> {
  const res = await fetch("/api/broker", { method: "DELETE", headers: authHeaders() });
  if (!res.ok) throw await failure(res, "Could not disconnect.");
  return (await res.json()) as BrokerStatus;
}

export async function listWatches(): Promise<WatchSummary[]> {
  const res = await fetch("/api/watches", { headers: authHeaders() });
  if (!res.ok) throw await failure(res, "Could not load watchers.");
  return ((await res.json()) as { watches: WatchSummary[] }).watches;
}

export async function mutateWatch(id: string, action: WatchAction): Promise<WatchSummary> {
  const res = await fetch(`/api/watches/${id}`, {
    method: "PATCH",
    headers: { ...authHeaders(), "content-type": "application/json" },
    body: JSON.stringify({ action }),
  });
  if (!res.ok) throw await failure(res, "Action failed.");
  return ((await res.json()) as { watch: WatchSummary }).watch;
}
