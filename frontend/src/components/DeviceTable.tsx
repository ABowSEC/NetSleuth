"use client"
import { useState } from "react"
import { DeviceRow } from "./DeviceRow"
import { getDeviceType } from "../lib/device-utils"
import type { Device, SortKey, Filter } from "../lib/types"

interface Props {
  devices: Record<string, Device>
  search: string
  activeFilter: Filter
  labels: Record<string, string>
  onSaveLabel: (ip: string, label: string) => void
}

export function DeviceTable({ devices, search, activeFilter, labels, onSaveLabel }: Props) {
  const [sortKey, setSortKey]   = useState<SortKey>("ip")
  const [sortAsc, setSortAsc]   = useState(true)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [editingIP, setEditing] = useState<string | null>(null)
  const [editValue, setEditVal] = useState("")

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(a => !a)
    else { setSortKey(key); setSortAsc(true) }
  }

  const toggleExpand = (ip: string) => setExpanded(prev => {
    const next = new Set(prev)
    next.has(ip) ? next.delete(ip) : next.add(ip)
    return next
  })

  let entries = Object.entries(devices).map(([ip, d]) => ({
    ip, device: d,
    label: labels[ip] || d.hostname || ip,
    type: getDeviceType(d.hostname),
  }))

  if (activeFilter !== "all") entries = entries.filter(e => e.type === activeFilter)
  if (search) {
    const q = search.toLowerCase()
    entries = entries.filter(e =>
      e.label.toLowerCase().includes(q) ||
      e.ip.toLowerCase().includes(q)    ||
      (e.device.mac || "").toLowerCase().includes(q)
    )
  }

  entries.sort((a, b) => {
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

  const SortTh = ({ label, sk }: { label: string; sk: SortKey }) => (
    <th
      onClick={() => handleSort(sk)}
      className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide cursor-pointer hover:text-indigo-600 select-none whitespace-nowrap"
    >
      {label}{sortKey === sk ? (sortAsc ? " v" : " ^") : ""}
    </th>
  )

  const total = Object.keys(devices).length

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 flex justify-between items-center">
        <span className="font-semibold text-gray-800 dark:text-white">Network Devices</span>
        <span className="text-xs text-gray-400">
          {entries.length} of {total} device{total !== 1 ? "s" : ""}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50 dark:bg-gray-750">
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
                  {total === 0 ? "No devices detected yet." : "No devices match the current filter."}
                </td>
              </tr>
            ) : entries.map(e => (
              <DeviceRow
                key={e.ip}
                ip={e.ip}
                device={e.device}
                label={e.label}
                type={e.type}
                expanded={expanded.has(e.ip)}
                isEditing={editingIP === e.ip}
                editValue={editValue}
                onToggle={() => toggleExpand(e.ip)}
                onEditStart={() => { setEditing(e.ip); setEditVal(e.label) }}
                onEditChange={setEditVal}
                onEditCommit={() => {
                  onSaveLabel(e.ip, editValue.trim() !== (e.device.hostname || e.ip) ? editValue.trim() : "")
                  setEditing(null)
                }}
                onEditCancel={() => setEditing(null)}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
