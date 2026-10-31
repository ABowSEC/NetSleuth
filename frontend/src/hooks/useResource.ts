"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useLive } from "@/context/LiveContext";
import { useVisibleInterval } from "./useVisibleInterval";

interface Resource<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
  /** Optimistically replace the data locally (e.g. after a successful edit). */
  setData: (update: (current: T | null) => T | null) => void;
}

/**
 * Fetch `load` on mount, whenever `key` changes, whenever live data changes
 * (debounced), and every `refreshMs` while the tab is visible. Only the newest
 * request may write state, so slow responses never overwrite newer ones.
 */
export function useResource<T>(
  key: string | null,
  load: (signal: AbortSignal) => Promise<T>,
  refreshMs: number | null = 30_000,
): Resource<T> {
  const { revision } = useLive();
  const [data, setDataState] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(key !== null);
  const loadRef = useRef(load);
  const current = useRef<AbortController | null>(null);

  useEffect(() => {
    loadRef.current = load;
  }, [load]);

  const run = useCallback(() => {
    if (key === null) return;
    current.current?.abort();
    const controller = new AbortController();
    current.current = controller;
    loadRef.current(controller.signal)
      .then((value) => {
        if (current.current !== controller) return;
        setDataState(value);
        setError(null);
      })
      .catch((err: unknown) => {
        if (current.current !== controller || controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "NetSleuth sent a response this page couldn't read.");
      })
      .finally(() => {
        if (current.current === controller) setLoading(false);
      });
  }, [key]);

  // Key changed: reset during render (React's pattern for state derived from props)...
  const [loadedKey, setLoadedKey] = useState(key);
  if (key !== loadedKey) {
    setLoadedKey(key);
    setDataState(null);
    setError(null);
    setLoading(key !== null);
  }

  // ...then load.
  useEffect(() => {
    run();
    return () => current.current?.abort();
  }, [run]);

  // Live updates: coalesce bursts of events into one refetch.
  const firstRevision = useRef(revision);
  useEffect(() => {
    if (revision === firstRevision.current) return;
    const timer = setTimeout(run, 800);
    return () => clearTimeout(timer);
  }, [revision, run]);

  useVisibleInterval(run, key === null ? null : refreshMs);

  const setData = useCallback((update: (c: T | null) => T | null) => setDataState(update), []);

  return { data, error, loading, reload: run, setData };
}
