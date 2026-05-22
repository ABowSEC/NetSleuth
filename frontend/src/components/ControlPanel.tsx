"use client"
import { FILTERS } from "../lib/device-utils"
import type { Filter } from "../lib/types"

interface Props {
  search: string
  onSearch: (v: string) => void
  activeFilter: Filter
  onFilter: (f: Filter) => void
  onExport: () => void
  onClearData: () => void
}

export function ControlPanel({ search, onSearch, activeFilter, onFilter, onExport, onClearData }: Props) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl px-4 py-3 shadow-sm mb-4 flex flex-wrap items-center gap-3">
      <input
        type="text"
        placeholder="Search by label, IP, or MAC..."
        value={search}
        onChange={e => onSearch(e.target.value)}
        className="flex-1 min-w-44 px-3 py-1.5 border border-gray-200 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg text-sm focus:outline-none focus:border-indigo-400"
      />
      <div className="flex gap-2 flex-wrap">
        {FILTERS.map(f => (
          <button
            key={f}
            onClick={() => onFilter(f as Filter)}
            className={`px-3 py-1 rounded-full text-xs border transition-all capitalize ${
              activeFilter === f
                ? "bg-indigo-600 text-white border-indigo-600"
                : "bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-600 hover:border-indigo-400 hover:text-indigo-600"
            }`}
          >
            {f}
          </button>
        ))}
      </div>
      <button onClick={onExport}    className="px-4 py-1.5 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 transition-colors">Export</button>
      <button onClick={onClearData} className="px-4 py-1.5 bg-red-500 text-white rounded-lg text-sm hover:bg-red-600 transition-colors">Clear Data</button>
    </div>
  )
}
