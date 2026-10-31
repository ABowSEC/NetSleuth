"use client"
import { useState } from "react"
import { DeviceRow } from "./DeviceRow"
import { getDeviceType, formatRelativeTime } from "../lib/device-utils"
import type { Device, SortKey, Filter } from "../lib/types"

interface Props {
  devices: Record<string, Device>
  search: string
  activeFilter: Filter
  onDeviceClaimed: () => void
}

function useSort() {
  const [sortKey, setSortKey] = useState<SortKey>("ip")
  const [sortAsc, setSortAsc] = useState(true)
  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(a => !a)
    else { setSortKey(key); setSortAsc(true) }
  }
  return { sortKey, sortAsc, handleSort }
}

function sortEntries(entries: ReturnType<typeof buildEntries>, sortKey: SortKey, sortAsc: boolean) {
  return [...entries].sort((a, b) => {
    const va = sortKey === "connections" ? a.device.connection_count
             : sortKey === "dns"         ? a.device.dns_count
             : sortKey === "label"       ? a.label
             : sortKey === "type"        ? a.type
             : sortKey === "ip"          ? a.ip
             : sortKey === "mac"         ? (a.device.mac || "")
             : a.device.last_seen ?? ""
    const vb = sortKey === "connections" ? b.device.connection_count
             : sortKey === "dns"         ? b.device.dns_count
             : sortKey === "label"       ? b.label
             : sortKey === "type"        ? b.type
             : sortKey === "ip"          ? b.ip
             : sortKey === "mac"         ? (b.device.mac || "")
             : b.device.last_seen ?? ""
    if (typeof va === "number" && typeof vb === "number") return sortAsc ? va - vb : vb - va
    return sortAsc ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va))
  })
}

function buildEntries(devices: Record<string, Device>) {
  return Object.entries(devices).map(([ip, d]) => ({
    ip, device: d,
    label: d.friendly_name || d.hostname || ip,
    type: getDeviceType(d.hostname),
  }))
}

const SortTh = ({ label, sk, sortKey, sortAsc, onSort }: {
  label: string; sk: SortKey; sortKey: SortKey; sortAsc: boolean
  onSort: (k: SortKey) => void
}) => (
  <th
    onClick={() => onSort(sk)}
    className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide cursor-pointer hover:text-indigo-600 select-none whitespace-nowrap"
  >
    {label}{sortKey === sk ? (sortAsc ? " ▾" : " ▴") : ""}
  </th>
)

function DeviceSection({ title, accent, entries, expanded, editingIP, editValue, sortKey, sortAsc, onSort,
  onToggle, onEditStart, onEditChange, onEditCommit, onEditCancel, onClaim }: {
  title: string; accent: string
  entries: ReturnType<typeof buildEntries>
  expanded: Set<string>; editingIP: string | null; editValue: string
  sortKey: SortKey; sortAsc: boolean; onSort: (k: SortKey) => void
  onToggle: (ip: string) => void; onEditStart: (ip: string, label: string) => void
  onEditChange: (v: string) => void; onEditCommit: (ip: string) => void
  onEditCancel: () => void; onClaim: (ip: string, name: string) => void
}) {
  if (entries.length === 0) return null
  return (
    <div className="mb-0">
      <div className={`px-4 py-2 text-xs font-semibold uppercase tracking-wider ${accent}`}>
        {title} ({entries.length})
      </div>
      <table className="w-full">
        <thead className="bg-gray-50 dark:bg-gray-750">
          <tr>
            <th className="w-7" />
            <SortTh label="Name"     sk="label"       sortKey={sortKey} sortAsc={sortAsc} onSort={onSort} />
            <SortTh label="Type"     sk="type"        sortKey={sortKey} sortAsc={sortAsc} onSort={onSort} />
            <SortTh label="IP"       sk="ip"          sortKey={sortKey} sortAsc={sortAsc} onSort={onSort} />
            <SortTh label="MAC"      sk="mac"         sortKey={sortKey} sortAsc={sortAsc} onSort={onSort} />
            <SortTh label="Conns"    sk="connections" sortKey={sortKey} sortAsc={sortAsc} onSort={onSort} />
            <SortTh label="DNS"      sk="dns"         sortKey={sortKey} sortAsc={sortAsc} onSort={onSort} />
            <SortTh label="Last Seen" sk="last_seen"  sortKey={sortKey} sortAsc={sortAsc} onSort={onSort} />
            <th className="w-8" />
          </tr>
        </thead>
        <tbody>
          {entries.map(e => (
            <DeviceRow
              key={e.ip}
              ip={e.ip}
              device={e.device}
              label={e.label}
              type={e.type}
              expanded={expanded.has(e.ip)}
              isEditing={editingIP === e.ip}
              editValue={editValue}
              onToggle={() => onToggle(e.ip)}
              onEditStart={() => onEditStart(e.ip, e.label)}
              onEditChange={onEditChange}
              onEditCommit={() => onEditCommit(e.ip)}
              onEditCancel={onEditCancel}
              onClaim={onClaim}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function DeviceTable({ devices, search, activeFilter, onDeviceClaimed }: Props) {
  const { sortKey, sortAsc, handleSort } = useSort()
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [editingIP, setEditing] = useState<string | null>(null)
  const [editValue, setEditVal] = useState("")

  const toggleExpand = (ip: string) => setExpanded(prev => {
    const next = new Set(prev); next.has(ip) ? next.delete(ip) : next.add(ip); return next
  })

  const handleClaim = async (ip: string, name: string) => {
    await fetch(`/api/devices/${ip}/claim`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    })
    onDeviceClaimed()
  }

  let entries = buildEntries(devices)
  if (activeFilter !== "all") entries = entries.filter(e => e.type === activeFilter)
  if (search) {
    const q = search.toLowerCase()
    entries = entries.filter(e =>
      e.label.toLowerCase().includes(q) ||
      e.ip.toLowerCase().includes(q) ||
      (e.device.mac || "").toLowerCase().includes(q)
    )
  }

  const unknown = sortEntries(entries.filter(e => !e.device.is_known), sortKey, sortAsc)
  const known   = sortEntries(entries.filter(e =>  e.device.is_known), sortKey, sortAsc)
  const total   = Object.keys(devices).length

  const rowProps = {
    expanded, editingIP, editValue, sortKey, sortAsc, onSort: handleSort,
    onToggle: toggleExpand,
    onEditStart: (ip: string, label: string) => { setEditing(ip); setEditVal(label) },
    onEditChange: setEditVal,
    onEditCommit: (ip: string) => {
      handleClaim(ip, editValue.trim())
      setEditing(null)
    },
    onEditCancel: () => setEditing(null),
    onClaim: handleClaim,
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 flex justify-between items-center">
        <span className="font-semibold text-gray-800 dark:text-white">Network Devices</span>
        <span className="text-xs text-gray-400">
          {entries.length} of {total} device{total !== 1 ? "s" : ""}
        </span>
      </div>

      <div className="overflow-x-auto divide-y divide-gray-100 dark:divide-gray-700">
        {unknown.length === 0 && known.length === 0 ? (
          <p className="py-12 text-center text-gray-400 italic text-sm">
            {total === 0 ? "No devices detected yet." : "No devices match the current filter."}
          </p>
        ) : (
          <>
            <DeviceSection title="Unknown Devices" accent="text-orange-600 bg-orange-50 dark:bg-orange-950/20 dark:text-orange-400" entries={unknown} {...rowProps} />
            <DeviceSection title="Known Devices"   accent="text-green-700 bg-green-50 dark:bg-green-950/20 dark:text-green-400"   entries={known}   {...rowProps} />
          </>
        )}
      </div>
    </div>
  )
}
