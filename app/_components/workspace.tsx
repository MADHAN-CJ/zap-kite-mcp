"use client";

import { LogOutIcon, RadarIcon, ZapIcon } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  type BrokerStatus,
  getBrokerStatus,
  listWatches,
  SessionExpiredError,
  type WatchSummary,
} from "@/lib/client/api";
import { clearSession, getUser, isLoggedIn } from "@/lib/client/session";
import { BrokerCard } from "./broker-card";
import { Login } from "./login";
import { WatchCard } from "./watch-card";

const LIVE = new Set(["ARMED", "PAUSED", "ERROR"]);
const MCP_URL = process.env.NEXT_PUBLIC_MCP_URL ?? "";

export function Workspace() {
  const [loggedIn, setLoggedIn] = useState<boolean | null>(null);
  const [broker, setBroker] = useState<BrokerStatus | null>(null);
  const [watches, setWatches] = useState<WatchSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const router = useRouter();
  const params = useSearchParams();

  const signOut = useCallback(() => {
    clearSession();
    setLoggedIn(false);
    setBroker(null);
    setWatches(null);
  }, []);

  const fail = useCallback(
    (e: unknown) => {
      if (e instanceof SessionExpiredError) {
        signOut();
        return;
      }
      setError(e instanceof Error ? e.message : "Something went wrong.");
    },
    [signOut],
  );

  const refresh = useCallback(async () => {
    try {
      const [status, rows] = await Promise.all([getBrokerStatus(), listWatches()]);
      setBroker(status);
      setWatches(rows);
      setError(null);
    } catch (e) {
      fail(e);
    }
  }, [fail]);

  useEffect(() => {
    setLoggedIn(isLoggedIn());
  }, []);

  useEffect(() => {
    if (!loggedIn) return;
    void refresh();
    const id = window.setInterval(() => void refresh(), 15_000);
    return () => window.clearInterval(id);
  }, [loggedIn, refresh]);

  useEffect(() => {
    const connected = params.get("connected");
    const err = params.get("error");
    if (!connected && !err) return;
    setNotice(
      connected ? "Zerodha connected. Claude can read this account until the session ends." : null,
    );
    setError(err);
    router.replace("/");
  }, [params, router]);

  if (loggedIn === null) return null;
  if (!loggedIn) return <Login onLoggedIn={() => setLoggedIn(true)} />;

  const live = (watches ?? []).filter((w) => LIVE.has(w.status));
  const done = (watches ?? []).filter((w) => !LIVE.has(w.status));
  const patch = (updated: WatchSummary) =>
    setWatches((prev) => prev?.map((w) => (w.id === updated.id ? updated : w)) ?? prev);

  return (
    <main className="min-h-dvh bg-background text-foreground">
      <div className="mx-auto flex max-w-2xl flex-col gap-6 p-5">
        <header className="flex items-center gap-3">
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ZapIcon className="size-4" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="font-medium text-lg tracking-tight">Slash Markets</h1>
            <p className="truncate text-muted-foreground text-xs">{getUser()?.email}</p>
          </div>
          <Button onClick={signOut} size="sm" variant="ghost">
            <LogOutIcon className="size-4" /> Sign out
          </Button>
        </header>

        {notice ? (
          <p className="rounded-md border border-emerald-600/40 bg-emerald-600/10 px-3 py-2 text-emerald-800 text-sm">
            {notice}
          </p>
        ) : null}
        {error ? (
          <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-destructive text-sm">
            {error}
          </p>
        ) : null}

        <BrokerCard onChanged={setBroker} onError={fail} status={broker} />

        {MCP_URL ? (
          <p className="text-muted-foreground text-xs">
            Claude connector URL: <code className="font-mono">{MCP_URL}</code>
          </p>
        ) : null}

        <section className="flex flex-col gap-3">
          <div>
            <h2 className="flex items-center gap-2 font-semibold">
              <RadarIcon className="size-4" /> Watchers
            </h2>
            <p className="text-muted-foreground text-sm">
              Background checks Claude set up for you. They run during market hours and email you
              when a condition becomes true. Ask Claude to create one.
            </p>
          </div>
          {watches === null && !error ? (
            <p className="text-muted-foreground text-sm">Loading…</p>
          ) : null}
          {watches !== null && watches.length === 0 ? (
            <p className="text-muted-foreground text-sm">No watchers yet.</p>
          ) : null}
          {live.map((w) => (
            <WatchCard key={w.id} onChanged={patch} watch={w} />
          ))}
          {done.length > 0 ? (
            <>
              <p className="pt-2 font-medium text-muted-foreground text-xs tracking-wider">
                FINISHED
              </p>
              <div className="flex flex-col gap-3 opacity-70">
                {done.map((w) => (
                  <WatchCard key={w.id} onChanged={patch} watch={w} />
                ))}
              </div>
            </>
          ) : null}
        </section>
      </div>
    </main>
  );
}
