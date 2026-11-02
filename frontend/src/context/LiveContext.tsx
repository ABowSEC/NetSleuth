"use client";

// One live connection per tab, shared by every page.
// Prefers the server-sent event stream; while that is down (or in mock mode)
// it polls, but only while the tab is visible.

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { toEvent, toIdentify, toSummary } from "@/lib/guards";
import type { Health, IdentifyStatus, NetEvent, Summary } from "@/lib/types";
import { useVisibleInterval } from "@/hooks/useVisibleInterval";
import { notifyIfWanted } from "@/lib/notifications";

export type LiveStatus = "connecting" | "live" | "polling" | "offline";

interface LiveState {
  status: LiveStatus;
  summary: Summary | null;
  health: Health | null;
  /** Bumps whenever server data changed; pages refetch when it does. */
  revision: number;
  setHealth: (health: Health) => void;
  /** Identify mode progress; idle when nothing is running. */
  identify: IdentifyStatus;
  setIdentify: (status: IdentifyStatus) => void;
  refresh: () => void;
}

export const IDLE_IDENTIFY: IdentifyStatus = {
  running: false, started_at: null, ends_at: null, done: 0, total: 0, current: null, port_check: false,
};

const LiveContext = createContext<LiveState>({
  status: "connecting", summary: null, health: null, revision: 0, setHealth: () => {},
  identify: IDLE_IDENTIFY, setIdentify: () => {}, refresh: () => {},
});

const POLL_MS = 10_000;
const HEALTH_MS = 30_000;
const IDENTIFY_POLL_MS = 2_000;

const loadBaseline = () => Promise.all([api.health(), api.summary(), api.events({ limit: 1 }), api.identify()]);

export function LiveProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<LiveStatus>("connecting");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [revision, setRevision] = useState(0);
  const [identify, setIdentifyState] = useState<IdentifyStatus>(IDLE_IDENTIFY);
  const lastEventId = useRef<number | null>(null);
  const streamUp = useRef(false);

  const bump = useCallback(() => setRevision((r) => r + 1), []);

  // When a run ends, what it learned changed device data: refetch.
  const setIdentify = useCallback((next: IdentifyStatus) => {
    setIdentifyState((prev) => {
      if (prev.running && !next.running) setTimeout(bump, 0);
      return next;
    });
  }, [bump]);

  const receive = useCallback((event: NetEvent, live: boolean) => {
    if (lastEventId.current !== null && event.id <= lastEventId.current) return;
    lastEventId.current = event.id;
    if (live) notifyIfWanted(event);
  }, []);

  // Baseline: health, summary and the newest event id (so old events never notify).
  const applyBaseline = useCallback(([h, s, latest, id]: [Health, Summary, NetEvent[], IdentifyStatus]) => {
    setHealth(h);
    setSummary(s);
    setIdentify(id);
    if (latest[0] && lastEventId.current === null) lastEventId.current = latest[0].id;
    if (!streamUp.current) setStatus(api.streamUrl ? "connecting" : "polling");
    bump();
  }, [bump, setIdentify]);
  const markOffline = useCallback(() => setStatus("offline"), []);

  const refresh = useCallback(() => {
    loadBaseline().then(applyBaseline, markOffline);
  }, [applyBaseline, markOffline]);

  useEffect(() => {
    loadBaseline().then(applyBaseline, markOffline);
  }, [applyBaseline, markOffline]);

  // Live stream
  useEffect(() => {
    if (!api.streamUrl || typeof EventSource === "undefined") return;
    const source = new EventSource(api.streamUrl);

    source.onopen = () => {
      streamUp.current = true;
      setStatus("live");
    };
    source.onerror = () => {
      // EventSource reconnects by itself (resuming with Last-Event-ID).
      streamUp.current = false;
      setStatus((s) => (s === "offline" ? s : "polling"));
    };
    source.addEventListener("event", (msg) => {
      try {
        receive(toEvent(JSON.parse((msg as MessageEvent).data)), true);
        bump();
      } catch {
        // ignore malformed frame
      }
    });
    source.addEventListener("identify", (msg) => {
      try {
        setIdentify(toIdentify(JSON.parse((msg as MessageEvent).data)));
      } catch {
        // ignore malformed frame
      }
    });
    source.addEventListener("summary", (msg) => {
      try {
        setSummary(toSummary(JSON.parse((msg as MessageEvent).data)));
        bump();
      } catch {
        // ignore malformed frame
      }
    });
    return () => source.close();
  }, [bump, receive, setIdentify]);

  // Fallback polling while the stream is down
  const poll = useCallback(async () => {
    if (streamUp.current) return;
    try {
      const since = lastEventId.current ?? undefined;
      const [s, fresh] = await Promise.all([api.summary(), api.events({ since, limit: 50 })]);
      setSummary(s);
      for (const event of [...fresh].reverse()) receive(event, since !== undefined);
      setStatus("polling");
      bump();
    } catch {
      setStatus("offline");
    }
  }, [bump, receive]);
  useVisibleInterval(poll, POLL_MS);

  useVisibleInterval(useCallback(() => {
    api.health().then(setHealth).catch(() => setStatus("offline"));
  }, []), HEALTH_MS);

  // Identify progress without the stream (or in mock mode): poll only while a run is active.
  useVisibleInterval(useCallback(() => {
    if (!streamUp.current) api.identify().then(setIdentify).catch(() => {});
  }, [setIdentify]), identify.running ? IDENTIFY_POLL_MS : null);

  return (
    <LiveContext.Provider value={{ status, summary, health, revision, setHealth, identify, setIdentify, refresh }}>
      {children}
    </LiveContext.Provider>
  );
}

export const useLive = () => useContext(LiveContext);
