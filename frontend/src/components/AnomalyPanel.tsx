"use client"
import { BarChart, Bar, ResponsiveContainer, XAxis, Tooltip } from "recharts"
import type { AnomalyEvent } from "../lib/types"

interface Props {
  anomalies: AnomalyEvent[]
}

function bucketByMinute(events: AnomalyEvent[]) {
  const counts: Record<string, number> = {}
  events.forEach(e => {
    const minute = new Date(e.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    counts[minute] = (counts[minute] ?? 0) + 1
  })
  return Object.entries(counts).slice(-15).map(([t, count]) => ({ t, count }))
}

export function AnomalyPanel({ anomalies }: Props) {
  const chartData = bucketByMinute(anomalies)

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm overflow-hidden mt-4">
      <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700">
        <span className="font-semibold text-gray-800 dark:text-white">ML Anomaly Detection</span>
      </div>

      {anomalies.length === 0 ? (
        <div className="py-6 px-4 text-center">
          <p className="text-sm text-gray-500 dark:text-gray-400">No anomalies detected.</p>
          <p className="text-xs text-gray-400 mt-1">
            If ML is inactive, run <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">python src/ml/train_model.py</code> to enable it.
          </p>
        </div>
      ) : (
        <>
          <div className="px-4 pt-3">
            <ResponsiveContainer width="100%" height={60}>
              <BarChart data={chartData} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                <XAxis dataKey="t" tick={{ fontSize: 9 }} interval="preserveStartEnd" />
                <Tooltip contentStyle={{ fontSize: 11 }} />
                <Bar dataKey="count" fill="#6366f1" radius={[2, 2, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="max-h-48 overflow-y-auto divide-y divide-gray-50 dark:divide-gray-700">
            {anomalies.slice(0, 50).map((a, i) => (
              <div key={i} className="px-4 py-2 flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-gray-400">{new Date(a.timestamp).toLocaleTimeString()}</span>
                  <span className="font-mono text-gray-600 dark:text-gray-300">
                    {a.src_ip}:{a.src_port} &rarr; {a.dst_ip}:{a.dst_port}
                  </span>
                  <span className="bg-gray-100 dark:bg-gray-700 text-gray-500 px-1.5 py-0.5 rounded">
                    {a.protocol}
                  </span>
                </div>
                <span className={`font-mono font-semibold ${a.score < -0.35 ? "text-red-600" : "text-yellow-600"}`}>
                  {a.score.toFixed(3)}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
