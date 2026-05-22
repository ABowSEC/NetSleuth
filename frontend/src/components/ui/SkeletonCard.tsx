export function SkeletonCard() {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm animate-pulse">
      <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mx-auto mb-2" />
      <div className="h-3 bg-gray-100 dark:bg-gray-600 rounded w-3/4 mx-auto" />
    </div>
  )
}

export function SkeletonTable() {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm overflow-hidden animate-pulse">
      <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700">
        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-32" />
      </div>
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="px-4 py-3 border-b border-gray-50 dark:border-gray-700 flex gap-4">
          <div className="h-3 bg-gray-100 dark:bg-gray-600 rounded w-24" />
          <div className="h-3 bg-gray-100 dark:bg-gray-600 rounded w-16" />
          <div className="h-3 bg-gray-100 dark:bg-gray-600 rounded w-28" />
        </div>
      ))}
    </div>
  )
}
