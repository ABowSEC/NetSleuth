"use client"

import { useState, useEffect } from "react"
import { useNetworkData }  from "../hooks/useNetworkData"
import { useSuspicious }   from "../hooks/useSuspicious"
import { useAnomalies }    from "../hooks/useAnomalies"
import { useNotifications } from "../hooks/useNotifications"
import { StatsCard }       from "../components/StatsCard"
import { ControlPanel }    from "../components/ControlPanel"
import { DeviceTable }     from "../components/DeviceTable"
import { AlertPanel }      from "../components/AlertPanel"
import { SuspiciousPanel } from "../components/SuspiciousPanel"
import { AnomalyPanel }    from "../components/AnomalyPanel"
import { ThemeToggle }     from "../components/ui/ThemeToggle"
import { ErrorBanner }     from "../components/ui/ErrorBanner"
import { SkeletonCard, SkeletonTable } from "../components/ui/SkeletonCard"
import type { Filter } from "../lib/types"

function getLabels(): Record<string, string> {
  try { return JSON.parse(localStorage.getItem("netsleuth_labels") || "{}") }
  catch { return {} }
}

export default function Dashboard() {
  const { data, isLoading, error, history, refetch } = useNetworkData()
  const { suspicious } = useSuspicious()
  const { anomalies }  = useAnomalies()
  const { permission, requestPermission } = useNotifications()

  const [search, setSearch]         = useState("")
  const [activeFilter, setFilter]   = useState<Filter>("all")
  const [labels, setLabels]         = useState<Record<string, string>>({})

  useEffect(() => { setLabels(getLabels()) }, [])

  const saveLabel = (ip: string, label: string) => {
    const next = { ...labels }
    if (label) next[ip] = label; else delete next[ip]
    setLabels(next)
    localStorage.setItem("netsleuth_labels", JSON.stringify(next))
  }

  const exportData = () => {
    if (!data) return
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement("a")
    a.href     = url
    a.download = `netsleuth_${new Date().toISOString().slice(0, 19).replace(/:/g, "-")}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const clearData = async () => {
    if (!confirm("Clear all device data?")) return
    await fetch("/api/clear-data", { method: "POST" })
    refetch()
  }

  const clearAlerts = async () => {
    await fetch("/api/alerts/clear", { method: "POST" })
    refetch()
  }

  const stats = [
    { label: "Devices",     value: data?.total_devices     ?? "--", key: "devices" as const,     accent: "#6366f1" },
    { label: "Connections", value: data?.total_connections  ?? "--", key: "connections" as const, accent: "#8b5cf6" },
    { label: "DNS Queries", value: data?.total_dns_queries  ?? "--", key: "dns" as const,         accent: "#a855f7" },
    { label: "Alerts",      value: (data?.alerts ?? []).length,      key: "alerts" as const,      accent: "#ef4444" },
    { label: "Last Update", value: data?.last_update        ?? "--:--", key: null,                accent: "#6366f1" },
  ]

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-500 to-purple-700 p-4">

      {/* Header */}
      <div className="text-center mb-4 relative">
        <h1 className="text-3xl font-bold text-white tracking-tight">NetSleuth</h1>
        <p className="text-indigo-200 text-sm mt-1">Real-time Network Monitoring</p>
        <div className="absolute right-0 top-0 flex items-center gap-2">
          {permission === "default" && (
            <button
              onClick={requestPermission}
              className="px-3 py-1 rounded-lg border border-white/30 text-white/80 text-xs hover:bg-white/10 transition-colors"
            >
              Enable Notifications
            </button>
          )}
          <ThemeToggle />
        </div>
      </div>

      {/* Error banner */}
      {error && <ErrorBanner message={error} onRetry={refetch} />}

      {/* Stats */}
      <div className="grid grid-cols-5 gap-3 mb-4">
        {isLoading && !data
          ? Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)
          : stats.map(s => (
              <StatsCard
                key={s.label}
                label={s.label}
                value={s.value}
                accent={s.accent}
                trend={s.key ? history.map(h => ({ value: h[s.key as keyof typeof h] as number })) : undefined}
              />
            ))
        }
      </div>

      {/* Controls */}
      <ControlPanel
        search={search}
        onSearch={setSearch}
        activeFilter={activeFilter}
        onFilter={setFilter}
        onExport={exportData}
        onClearData={clearData}
      />

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4 items-start">

        {/* Device table */}
        {isLoading && !data ? (
          <SkeletonTable />
        ) : (
          <DeviceTable
            devices={data?.devices ?? {}}
            search={search}
            activeFilter={activeFilter}
            labels={labels}
            onSaveLabel={saveLabel}
          />
        )}

        {/* Right sidebar */}
        <div>
          <AlertPanel alerts={data?.alerts ?? []} onClear={clearAlerts} />
          <SuspiciousPanel devices={suspicious} />
        </div>

      </div>

      {/* Anomaly panel — full width below */}
      <div className="mt-4">
        <AnomalyPanel anomalies={anomalies} />
      </div>

      <p className="text-center text-indigo-200 text-xs mt-4">
        <span className="inline-block w-2 h-2 rounded-full bg-green-400 mr-1.5 animate-pulse align-middle" />
        Auto-updating every 5 seconds
      </p>

    </div>
  )
}
