"use client"
import { useState, useEffect, useCallback } from "react"

export interface PollingResult<T> {
  data: T | null
  isLoading: boolean
  error: string | null
  refetch: () => void
}

export function usePollingFetch<T>(url: string, intervalMs = 5000): PollingResult<T> {
  const [data, setData]         = useState<T | null>(null)
  const [isLoading, setLoading] = useState(true)
  const [error, setError]       = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setData(await res.json())
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch")
    } finally {
      setLoading(false)
    }
  }, [url])

  useEffect(() => {
    fetchData()
    const id = setInterval(fetchData, intervalMs)
    return () => clearInterval(id)
  }, [fetchData, intervalMs])

  return { data, isLoading, error, refetch: fetchData }
}
