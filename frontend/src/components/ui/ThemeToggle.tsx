"use client"
import { useTheme } from "../../context/ThemeContext"
import type { Theme } from "../../lib/types"

const CYCLE: Record<Theme, Theme> = { light: "dark", dark: "system", system: "light" }
const LABEL: Record<Theme, string> = { light: "Light", dark: "Dark", system: "System" }

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  return (
    <button
      onClick={() => setTheme(CYCLE[theme])}
      className="px-3 py-1 rounded-lg border border-white/30 text-white/80 text-xs hover:bg-white/10 transition-colors"
      title="Toggle theme"
    >
      {LABEL[theme]}
    </button>
  )
}
