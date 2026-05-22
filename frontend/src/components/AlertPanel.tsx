"use client"
import { SEVERITY_COLORS } from "../lib/device-utils"
import type { Alert } from "../lib/types"

interface Props {
  alerts: Alert[]
  onClear: () => void
}

export function AlertPanel({ alerts, onClear }: Props) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 flex justify-between items-center">
        <span className="font-semibold text-gray-800 dark:text-white">Alerts</span>
        <button onClick={onClear} className="px-3 py-1 bg-indigo-600 text-white rounded-lg text-xs hover:bg-indigo-700 transition-colors">
          Clear
        </button>
      </div>
      <div className="max-h-80 overflow-y-auto">
        {alerts.length === 0 ? (
          <p className="py-8 text-center text-gray-400 italic text-sm">No alerts at this time.</p>
        ) : (
          [...alerts].reverse().slice(0, 50).map((a, i) => (
            <div key={i} className={`mx-3 my-2 px-3 py-2 border-l-4 rounded-r-lg ${SEVERITY_COLORS[a.severity]}`}>
              <div className="text-xs text-gray-400">{new Date(a.timestamp).toLocaleTimeString()}</div>
              <div className="text-sm font-semibold leading-snug mt-0.5">{a.message}</div>
              <div className="text-xs text-gray-400 mt-1">{a.type} · {a.severity}</div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
