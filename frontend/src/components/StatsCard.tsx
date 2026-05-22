"use client"
import { AreaChart, Area, ResponsiveContainer } from "recharts"

interface Props {
  label: string
  value: string | number
  trend?: { value: number }[]
  accent?: string
}

export function StatsCard({ label, value, trend, accent = "#6366f1" }: Props) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm text-center">
      <div className="text-2xl font-bold text-indigo-600 dark:text-indigo-400">{value}</div>
      <div className="text-xs text-gray-400 uppercase tracking-wide mt-1">{label}</div>
      {trend && trend.length > 1 && (
        <div className="mt-2 -mx-1">
          <ResponsiveContainer width="100%" height={32}>
            <AreaChart data={trend} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id={`grad-${label}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={accent} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={accent} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="value"
                stroke={accent}
                strokeWidth={1.5}
                fill={`url(#grad-${label})`}
                dot={false}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
