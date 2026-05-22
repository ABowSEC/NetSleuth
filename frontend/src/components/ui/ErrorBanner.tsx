interface Props {
  message: string
  onRetry: () => void
}

export function ErrorBanner({ message, onRetry }: Props) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 mb-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="text-red-500 font-bold text-sm">!</span>
        <div>
          <p className="text-sm font-semibold text-red-800">Backend unreachable</p>
          <p className="text-xs text-red-600">{message} — is NetSleuth running?</p>
        </div>
      </div>
      <button
        onClick={onRetry}
        className="px-3 py-1.5 bg-red-600 text-white text-xs rounded-lg hover:bg-red-700 transition-colors"
      >
        Retry
      </button>
    </div>
  )
}
