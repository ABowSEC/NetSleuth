import { TYPE_LABELS, TYPE_COLORS, SEVERITY_BADGE } from "../../lib/device-utils"
import type { DeviceType, Severity } from "../../lib/types"

export function DeviceBadge({ type }: { type: DeviceType }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold uppercase ${TYPE_COLORS[type]}`}>
      {TYPE_LABELS[type]}
    </span>
  )
}

export function SeverityBadge({ level }: { level: Severity | "NORMAL" }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold uppercase ${SEVERITY_BADGE[level]}`}>
      {level}
    </span>
  )
}
