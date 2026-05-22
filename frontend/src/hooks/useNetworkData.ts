"use client"
import { useState, useEffect, useCallback, useRef } from "react"
import type { NetworkData, TrendPoint } from "../lib/types"

export function useNetworkData() {
  const [data, setData]         = useState<NetworkData | null>(null)
  const [isLoading, setLoading] = useState(true)
  const [error, setError]       = useState<string | null>(null)
  const [history, setHistory]   = useState<TrendPoint[]>([])
  const notifiedRef             = useRef<Set<string>>(new Set())

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch("/api/network-data")
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const d: NetworkData = await res.json()
      setData(d)
      setError(null)
      setHistory(prev => [
        ...prev.slice(-19),
        { t: Date.now(), devices: d.total_devices, connections: d.total_connections, dns: d.total_dns_queries, alerts: d.alerts.length },
      ])
      // Browser notifications for new CRITICAL alerts
      if (typeof window !== "undefined" && Notification.permission === "granted") {
        d.alerts
          .filter(a => a.severity === "CRITICAL" && !notifiedRef.current.has(a.timestamp))
          .forEach(a => {
            notifiedRef.current.add(a.timestamp)
            new Notification("NetSleuth: Critical Alert", { body: a.message, icon: "/favicon.ico" })
          })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const id = setInterval(fetchData, 5000)
    return () => clearInterval(id)
  }, [fetchData])

  return { data, isLoading, error, history, refetch: fetchData }
}
