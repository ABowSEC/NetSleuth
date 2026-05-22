"use client"

import { useState, useEffect, useCallback, Fragment } from "react"

type Severity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
type DeviceType = "apple" | "router" | "tv" | "dns" | "gaming" | "other"
type SortKey = "label" | "type" | "ip" | "mac" | "connections" | "dns" | "last_seen"
type Filter = DeviceType | "all"

interface Device {
  hostname: string
  mac: string
  dns_queries: string[]
  connections: string[]
  services: string[]
  last_seen: string
  connection_count: number
  dns_count: number
}

interface Alert {
  timestamp: string
  message: string
  type: string
  severity: Severity
}

interface NetworkData {
  devices: Record<string, Device>
  last_update: string | null
  total_devices: number
  total_connections: number
  total_dns_queries: number
  alerts: Alert[]
}

function getDeviceType(hostname: string): DeviceType {
  const h = (hostname || "").toLowerCase()
  if (h.includes("apple") || h.includes("iphone") || h.includes("ipad") || h.includes("macbook") || h.includes("airpods") || h.includes("homepod")) return "apple"
  if (h.includes("router") || h.includes("gateway") || h.includes("linksys") || h.includes("netgear") || h.includes("access point")) return "router"
  if (h.includes("smart tv") || h.includes(" tv") || h.includes("roku") || h.includes("lg tv") || h.includes("samsung tv") || h.includes("fire tv") || h.includes("chromecast")) return "tv"
  if (h.includes("dns server") || h.includes("pihole") || h.includes("dns")) return "dns"
  if (h.includes("xbox") || h.includes("playstation") || h.includes("nintendo") || h.includes("steam deck")) return "gaming"
  return "other"
}

const TYPE_LABELS: Record<DeviceType, string> = { apple: "Apple", router: "Router", tv: "TV", dns: "DNS", gaming: "Gaming", other: "Other" }
const TYPE_COLORS: Record<DeviceType, string> = {
  apple:  "bg-green-100 text-green-800",
  router: "bg-blue-100 text-blue-800",
  tv:     "bg-orange-100 text-orange-800",
  dns:    "bg-purple-100 text-purple-800",
  gaming: "bg-red-100 text-red-800",
  other:  "bg-gray-100 text-gray-600",
}
const SEVERITY_COLORS: Record<Severity, string> = {
  LOW:      "border-blue-400 bg-blue-50",
  MEDIUM:   "border-yellow-400 bg-yellow-50",
  HIGH:     "border-red-400 bg-red-50",
  CRITICAL: "border-purple-500 bg-purple-50",
}
const FILTERS: Filter[] = ["all", "apple", "router", "tv", "dns", "gaming", "other"]

export default function Dashboard() {
  const [data, setData]               = useState<NetworkData | null>(null)
  const [search, setSearch]           = useState("")
  const [activeFilter, setFilter]     = useState<Filter>("all")
  const [sortKey, setSortKey]         = useState<SortKey>("ip")
  const [sortAsc, setSortAsc]         = useState(true)
  const [expandedIPs, setExpanded]    = useState<Set<string>>(new Set())
  const [labels, setLabels]           = useState<Record<string, string>>({})
  const [editingIP, setEditingIP]     = useState<string | null>(null)
  const [editValue, setEditValue]     = useState("")

  useEffect(() => {
    try {
      const stored = localStorage.getItem("netsleuth_labels")
      if (stored) setLabels(JSON.parse(stored))
    } catch {}
  }, [])

  const saveLabel = (ip: string, label: string) => {
    const next = { ...labels }
    if (label) next[ip] = label; else delete next[ip]
    setLabels(next)
    localStorage.setItem("netsleuth_labels", JSON.stringify(next))
  }

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch("/api/network-data")
      if (res.ok) setData(await res.json())
    } catch {}
  }, [])

  useEffect(() => {
    fetchData()
    const id = setInterval(fetchData, 5000)
    return () => clearInterval(id)
  }, [fetchData])

  const toggleExpand = (ip: string) => setExpanded(prev => {
    const next = new Set(prev)
    next.has(ip) ? next.delete(ip) : next.add(ip)
    return next
  })

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(a => !a)
    else { setSortKey(key); setSortAsc(true) }
  }

  const clearData = async () => {
    if (!confirm("Clear all device data?")) return
    await fetch("/api/clear-data", { method: "POST" })
    fetchData()
  }

  const clearAlerts = async () => {
    await fetch("/api/alerts/clear", { method: "POST" })
    fetchData()
  }

  const exportData = async () => {
    const res  = await fetch("/api/network-data")
    const blob = new Blob([JSON.stringify(await res.json(), null, 2)], { type: "application/json" })
    const url  = URL.createObjectURL(blob)
    const a    = Object.assign(document.createElement("a"), { href: url, download: `netsleuth_${new Date().toISOString().slice(0,19).replace(/:/g,"-")}.json` })
    a.click()
    URL.revokeObjectURL(url)
  }

  const devices = data?.devices ?? {}
  const alerts  = data?.alerts  ?? []

  let entries = Object.entries(devices).map(([ip, d]) => ({
    ip, ...d,
    label: labels[ip] || d.hostname || ip,
    type:  getDeviceType(d.hostname),
  }))

  if (activeFilter !== "all") entries = entries.filter(e => e.type === activeFilter)
  if (search) {
    const q = search.toLowerCase()
    entries = entries.filter(e =>
      e.label.toLowerCase().includes(q) ||
      e.ip.toLowerCase().includes(q)    ||
      (e.mac || "").toLowerCase().includes(q)
    )
  }

  entries.sort((a, b) => {
    const va = sortKey === "connections" ? a.connection_count : sortKey === "dns" ? a.dns_count : (a as Record<string, unknown>)[sortKey] ?? ""
    const vb = sortKey === "connections" ? b.connection_count : sortKey === "dns" ? b.dns_count : (b as Record<string, unknown>)[sortKey] ?? ""
    if (typeof va === "number" && typeof vb === "number") return sortAsc ? va - vb : vb - va
    return sortAsc ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va))
  })

  const SortTh = ({ label, sk }: { label: string; sk: SortKey }) => (
    <th onClick={() => handleSort(sk)}
      className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide cursor-pointer hover:text-indigo-600 select-none whitespace-nowrap">
      {label}{sortKey === sk ? (sortAsc ? " ↓" : " ↑") : ""}
    </th>
  )

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-500 to-purple-700 p-4">

      <div className="text-center mb-4">
        <h1 className="text-3xl font-bold text-white tracking-tight">NetSleuth</h1>
        <p className="text-indigo-200 text-sm mt-1">Real-time Network Monitoring</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-5 gap-3 mb-4">
        {([
          ["Devices",     data?.total_devices     ?? "--"],
          ["Connections", data?.total_connections  ?? "--"],
          ["DNS Queries", data?.total_dns_queries  ?? "--"],
          ["Alerts",      alerts.length],
          ["Last Update", data?.last_update        ?? "--:--"],
        ] as [string, string | number][]).map(([label, value]) => (
          <div key={label} className="bg-white rounded-xl p-4 text-center shadow-sm">
            <div className="text-2xl font-bold text-indigo-600">{value}</div>
            <div className="text-xs text-gray-400 uppercase tracking-wide mt-1">{label}</div>
          </div>
        ))}
      </div>

      {/* Controls */}
      <div className="bg-white rounded-xl px-4 py-3 shadow-sm mb-4 flex flex-wrap items-center gap-3">
        <input
          type="text"
          placeholder="Search by label, IP, or MAC..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1 min-w-44 px-3 py-1.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-indigo-400"
        />
        <div className="flex gap-2 flex-wrap">
          {FILTERS.map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded-full text-xs border transition-all capitalize ${
                activeFilter === f
                  ? "bg-indigo-600 text-white border-indigo-600"
                  : "bg-gray-50 text-gray-600 border-gray-200 hover:border-indigo-400 hover:text-indigo-600"
              }`}>
              {f}
            </button>
          ))}
        </div>
        <button onClick={exportData} className="px-4 py-1.5 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 transition-colors">Export</button>
        <button onClick={clearData}  className="px-4 py-1.5 bg-red-500 text-white rounded-lg text-sm hover:bg-red-600 transition-colors">Clear Data</button>
      </div>

      {/* Main grid */}
      <div className="grid gap-4 items-start" style={{ gridTemplateColumns: "1fr 300px" }}>

        {/* Device table */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 flex justify-between items-center">
            <span className="font-semibold text-gray-800">Network Devices</span>
            <span className="text-xs text-gray-400">
              {entries.length} of {Object.keys(devices).length} device{Object.keys(devices).length !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="w-7" />
                  <SortTh label="Label"     sk="label" />
                  <SortTh label="Type"      sk="type" />
                  <SortTh label="IP"        sk="ip" />
                  <SortTh label="MAC"       sk="mac" />
                  <SortTh label="Conns"     sk="connections" />
                  <SortTh label="DNS"       sk="dns" />
                  <SortTh label="Last Seen" sk="last_seen" />
                </tr>
              </thead>
              <tbody>
                {entries.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-gray-400 italic text-sm">
                      {Object.keys(devices).length === 0 ? "No devices detected yet." : "No devices match the current filter."}
                    </td>
                  </tr>
                ) : entries.map(e => {
                  const expanded  = expandedIPs.has(e.ip)
                  const isEditing = editingIP === e.ip
                  return (
                    <Fragment key={e.ip}>
                      <tr
                        className={`border-b border-gray-50 cursor-pointer transition-colors ${expanded ? "bg-indigo-50" : "hover:bg-gray-50"}`}
                        onClick={() => toggleExpand(e.ip)}
                      >
                        <td className="pl-3 text-gray-300 text-xs">{expanded ? "▼" : "▶"}</td>
                        <td className="px-3 py-2.5" onClick={ev => ev.stopPropagation()}>
                          {isEditing ? (
                            <input autoFocus
                              className="text-sm font-semibold border border-indigo-400 rounded px-1 py-0.5 w-36 outline-none"
                              value={editValue}
                              onChange={ev => setEditValue(ev.target.value)}
                              onBlur={() => {
                                saveLabel(e.ip, editValue !== (devices[e.ip]?.hostname || e.ip) ? editValue.trim() : "")
                                setEditingIP(null)
                              }}
                              onKeyDown={ev => {
                                if (ev.key === "Enter")  ev.currentTarget.blur()
                                if (ev.key === "Escape") setEditingIP(null)
                              }}
                            />
                          ) : (
                            <span
                              className="text-sm font-semibold text-gray-800 border-b border-dashed border-transparent hover:border-indigo-400 cursor-text"
                              onDoubleClick={() => { setEditingIP(e.ip); setEditValue(e.label) }}
                              title="Double-click to rename"
                            >
                              {e.label}
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold uppercase ${TYPE_COLORS[e.type]}`}>
                            {TYPE_LABELS[e.type]}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 font-mono text-xs text-gray-600">{e.ip}</td>
                        <td className="px-3 py-2.5 font-mono text-xs text-gray-500">{e.mac || "Unknown"}</td>
                        <td className="px-3 py-2.5">
                          <span className="px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded-full text-xs font-semibold">{e.connection_count}</span>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className="px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded-full text-xs font-semibold">{e.dns_count}</span>
                        </td>
                        <td className="px-3 py-2.5 text-xs text-gray-400">{e.last_seen || "--"}</td>
                      </tr>

                      {expanded && (
                        <tr className="bg-indigo-50/50">
                          <td colSpan={8} className="px-6 py-3">
                            <div className="grid grid-cols-3 gap-4">
                              {([ ["Connections", e.connections], ["DNS Queries", e.dns_queries], ["Services", e.services] ] as [string, string[]][]).map(([title, items]) => (
                                <div key={title}>
                                  <h4 className="text-xs uppercase tracking-wide text-gray-400 font-medium mb-2">{title} ({items?.length ?? 0})</h4>
                                  {items?.length ? (
                                    <ul className="space-y-0.5 max-h-28 overflow-y-auto">
                                      {items.slice(0, 25).map((item, i) => (
                                        <li key={i} className="text-xs text-gray-600 truncate border-b border-gray-100 py-0.5" title={item}>{item}</li>
                                      ))}
                                    </ul>
                                  ) : (
                                    <span className="text-xs text-gray-300 italic">None recorded</span>
                                  )}
                                </div>
                              ))}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Alerts */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 flex justify-between items-center">
            <span className="font-semibold text-gray-800">Alerts</span>
            <button onClick={clearAlerts} className="px-3 py-1 bg-indigo-600 text-white rounded-lg text-xs hover:bg-indigo-700 transition-colors">Clear</button>
          </div>
          <div className="max-h-[640px] overflow-y-auto">
            {alerts.length === 0 ? (
              <p className="py-8 text-center text-gray-400 italic text-sm">No alerts at this time.</p>
            ) : [...alerts].reverse().slice(0, 50).map((a, i) => (
              <div key={i} className={`mx-3 my-2.5 px-3 py-2 border-l-4 rounded-r-lg ${SEVERITY_COLORS[a.severity]}`}>
                <div className="text-xs text-gray-400">{new Date(a.timestamp).toLocaleTimeString()}</div>
                <div className="text-sm font-semibold text-gray-800 leading-snug mt-0.5">{a.message}</div>
                <div className="text-xs text-gray-400 mt-1">{a.type} · {a.severity}</div>
              </div>
            ))}
          </div>
        </div>

      </div>

      <p className="text-center text-indigo-200 text-xs mt-4">
        <span className="inline-block w-2 h-2 rounded-full bg-green-400 mr-1.5 animate-pulse align-middle" />
        Auto-updating every 5 seconds
      </p>

    </div>
  )
}
