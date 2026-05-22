"use client"
import { usePollingFetch } from "./usePollingFetch"
import type { AnomalyEvent } from "../lib/types"

export function useAnomalies() {
  const { data, error } = usePollingFetch<AnomalyEvent[]>("/api/anomalies", 10_000)
  return { anomalies: data ?? [], error }
}
