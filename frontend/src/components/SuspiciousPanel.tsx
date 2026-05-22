"use client"
import { SeverityBadge } from "./ui/Badge"
import type { SuspiciousDevice } from "../lib/types"

interface Props {
  devices: SuspiciousDevice[]
}

export function SuspiciousPanel({ devices }: Props) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm overflow-hidden mt-4">
      <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700">
        <span className="font-semibold text-gray-800 dark:text-white">Suspicious Devices</span>
      </div>
      <div className="max-h-64 overflow-y-auto">
        {devices.length === 0 ? (
          <p className="py-6 text-center text-gray-400 italic text-sm">No suspicious activity detected.</p>
        ) : (
          devices.map(d => {
            const risk = Math.min(1, Math.abs(d.score ?? 0) / 0.70)
            return (
              <div key={d.ip} className="px-4 py-2.5 border-b border-gray-50 dark:border-gray-700 last:border-0">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-xs text-gray-700 dark:text-gray-300">{d.ip}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">{d.total_anomalies} events</span>
                    <SeverityBadge level={d.level as "NORMAL" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"} />
                  </div>
                </div>
                <div className="h-1.5 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      d.level === "CRITICAL" ? "bg-purple-500" :
                      d.level === "HIGH"     ? "bg-red-500" :
                      d.level === "MEDIUM"   ? "bg-yellow-400" : "bg-blue-400"
                    }`}
                    style={{ width: `${risk * 100}%` }}
                  />
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
