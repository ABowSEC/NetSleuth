"use client"
import { Fragment } from "react"
import { DeviceBadge } from "./ui/Badge"
import { formatRelativeTime } from "../lib/device-utils"
import type { Device, DeviceType } from "../lib/types"

interface Props {
  ip: string
  device: Device
  label: string
  type: DeviceType
  expanded: boolean
  isEditing: boolean
  editValue: string
  onToggle: () => void
  onEditStart: () => void
  onEditChange: (v: string) => void
  onEditCommit: () => void
  onEditCancel: () => void
}

export function DeviceRow({
  ip, device, label, type, expanded, isEditing, editValue,
  onToggle, onEditStart, onEditChange, onEditCommit, onEditCancel,
}: Props) {
  return (
    <Fragment>
      <tr
        className={`border-b border-gray-50 dark:border-gray-700 cursor-pointer transition-colors ${
          expanded ? "bg-indigo-50 dark:bg-indigo-950/30" : "hover:bg-gray-50 dark:hover:bg-gray-750"
        }`}
        onClick={onToggle}
      >
        <td className="pl-3 text-gray-300 text-xs select-none">{expanded ? "v" : ">"}</td>

        <td className="px-3 py-2.5" onClick={e => e.stopPropagation()}>
          {isEditing ? (
            <input
              autoFocus
              className="text-sm font-semibold border border-indigo-400 rounded px-1 py-0.5 w-36 outline-none dark:bg-gray-700 dark:text-white"
              value={editValue}
              onChange={e => onEditChange(e.target.value)}
              onBlur={onEditCommit}
              onKeyDown={e => {
                if (e.key === "Enter")  e.currentTarget.blur()
                if (e.key === "Escape") onEditCancel()
              }}
            />
          ) : (
            <span
              className="text-sm font-semibold text-gray-800 dark:text-gray-100 border-b border-dashed border-transparent hover:border-indigo-400 cursor-text"
              onDoubleClick={onEditStart}
              title="Double-click to rename"
            >
              {label}
            </span>
          )}
        </td>

        <td className="px-3 py-2.5"><DeviceBadge type={type} /></td>
        <td className="px-3 py-2.5 font-mono text-xs text-gray-600 dark:text-gray-400">{ip}</td>
        <td className="px-3 py-2.5 font-mono text-xs text-gray-500 dark:text-gray-500">{device.mac || "Unknown"}</td>
        <td className="px-3 py-2.5">
          <span className="px-2 py-0.5 bg-indigo-50 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400 rounded-full text-xs font-semibold">
            {device.connection_count}
          </span>
        </td>
        <td className="px-3 py-2.5">
          <span className="px-2 py-0.5 bg-indigo-50 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400 rounded-full text-xs font-semibold">
            {device.dns_count}
          </span>
        </td>
        <td className="px-3 py-2.5 text-xs text-gray-400">{formatRelativeTime(device.last_seen)}</td>
      </tr>

      {expanded && (
        <tr className="bg-indigo-50/50 dark:bg-indigo-950/20">
          <td colSpan={8} className="px-6 py-3">
            <div className="grid grid-cols-3 gap-4">
              {([
                ["Connections", device.connections],
                ["DNS Queries", device.dns_queries],
                ["Services",    device.services],
              ] as [string, string[]][]).map(([title, items]) => (
                <div key={title}>
                  <h4 className="text-xs uppercase tracking-wide text-gray-400 font-medium mb-2">
                    {title} ({items?.length ?? 0})
                  </h4>
                  {items?.length ? (
                    <ul className="space-y-0.5 max-h-28 overflow-y-auto">
                      {items.slice(0, 25).map((item, i) => (
                        <li key={i} className="text-xs text-gray-600 dark:text-gray-400 truncate border-b border-gray-100 dark:border-gray-700 py-0.5" title={item}>
                          {item}
                        </li>
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
}
