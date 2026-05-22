"use client"
import { usePollingFetch } from "./usePollingFetch"
import type { SuspiciousDevice } from "../lib/types"

export function useSuspicious() {
  const { data, error } = usePollingFetch<SuspiciousDevice[]>("/api/suspicious", 10_000)
  return { suspicious: data ?? [], error }
}
