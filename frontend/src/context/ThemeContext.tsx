"use client"
import { createContext, useContext, useEffect, useState } from "react"
import type { Theme } from "../lib/types"

interface ThemeContextValue {
  theme: Theme
  setTheme: (t: Theme) => void
}

const ThemeContext = createContext<ThemeContextValue>({ theme: "system", setTheme: () => {} })

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("system")
  const [mounted, setMounted]  = useState(false)

  useEffect(() => {
    setMounted(true)
    const stored = localStorage.getItem("netsleuth_theme") as Theme | null
    if (stored) setThemeState(stored)
  }, [])

  useEffect(() => {
    if (!mounted) return
    const root = document.documentElement
    if (theme === "dark")  root.setAttribute("data-theme", "dark")
    else if (theme === "light") root.setAttribute("data-theme", "light")
    else root.removeAttribute("data-theme")
  }, [theme, mounted])

  const setTheme = (t: Theme) => {
    setThemeState(t)
    localStorage.setItem("netsleuth_theme", t)
  }

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export const useTheme = () => useContext(ThemeContext)
