"use client"

import { useState, useEffect } from "react"
import { useNetworkData }   from "../hooks/useNetworkData"
import { useNotifications } from "../hooks/useNotifications"
import { StatsCard }        from "../components/StatsCard"
import { ControlPanel }     from "../components/ControlPanel"
import { DeviceTable }      from "../components/DeviceTable"
import { AlertPanel }       from "../components/AlertPanel"
import { ThemeToggle }      from "../components/ui/ThemeToggle"
import { ErrorBanner }      from "../components/ui/ErrorBanner"
import { SkeletonCard, SkeletonTable } from "../components/ui/SkeletonCard"
import type { Filter } from "../lib/types"

export default function Dashboard() {
  const { data, isLoading, error, history, refetch } = useNetworkData()
  const { permission, requestPermission } = useNotifications()

  const [search, setSearch]       = useState("")
  const [activeFilter, setFilter] = useState<Filter>("all")

  const exportData = () => {
    if (!data) return
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement("a")
    a.href     = url
    a.download = `netsleuth_${new Date().toISOString().slice(0, 19).replace(/:/g, "-")}.json`
    document.body.appendChild(a); a.click()
    document.body.removeChild(a); URL.revokeObjectURL(url)
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

  const unknownCount = data?.unknown_devices ?? 0

  const stats = [
    { label: "Devices",     value: data?.total_devices    ?? "--", key: "devices" as const,     accent: "#6366f1" },
    { label: "Unknown",     value: unknownCount,                   key: null,                   accent: unknownCount > 0 ? "#f97316" : "#22c55e" },
    { label: "Connections", value: data?.total_connections ?? "--", key: "connections" as const, accent: "#8b5cf6" },
    { label: "DNS Queries", value: data?.total_dns_queries ?? "--", key: "dns" as const,         accent: "#a855f7" },
    { label: "Last Update", value: data?.last_update       ?? "--:--", key: null,               accent: "#6366f1" },
  ]

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-500 to-purple-700 p-4">

      {/* Header */}
      <div className="text-center mb-4 relative">
        <h1 className="text-3xl font-bold text-white tracking-tight">NetSleuth</h1>
        <p className="text-indigo-200 text-sm mt-1">Home Network Monitor</p>
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

      {error && <ErrorBanner message={error} onRetry={refetch} />}

      {/* Unknown device banner */}
      {unknownCount > 0 && (
        <div className="mb-4 px-4 py-3 rounded-xl bg-orange-500/90 text-white flex items-center gap-3 shadow">
          <span className="text-xl">⚠</span>
          <span className="font-semibold">
            {unknownCount} unknown device{unknownCount !== 1 ? "s" : ""} on your network
          </span>
          <span className="text-orange-100 text-sm">— scroll down to name them</span>
        </div>
      )}

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

        {isLoading && !data ? (
          <SkeletonTable />
        ) : (
          <DeviceTable
            devices={data?.devices ?? {}}
            search={search}
            activeFilter={activeFilter}
            onDeviceClaimed={refetch}
          />
        )}

        <AlertPanel alerts={data?.alerts ?? []} onClear={clearAlerts} />

      </div>

      <p className="text-center text-indigo-200 text-xs mt-4">
        <span className="inline-block w-2 h-2 rounded-full bg-green-400 mr-1.5 animate-pulse align-middle" />
        Auto-updating every 5 seconds
      </p>

    </div>
  )
}
