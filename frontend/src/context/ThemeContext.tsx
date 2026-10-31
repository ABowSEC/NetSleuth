"use client";

import { createContext, useCallback, useContext, useEffect, useSyncExternalStore } from "react";

export type ThemeMode = "light" | "dark" | "system";

export const THEME_STORAGE_KEY = "netsleuth_theme";

/**
 * Runs in <head> before first paint so the page never flashes the wrong theme.
 * Kept as a string because it executes before React loads.
 */
export const THEME_BOOT_SCRIPT = `(function(){try{var m=localStorage.getItem("${THEME_STORAGE_KEY}");
var d=m==="dark"||(m!=="light"&&matchMedia("(prefers-color-scheme: dark)").matches);
document.documentElement.dataset.theme=d?"dark":"light";}catch(e){document.documentElement.dataset.theme="light";}})();`;

interface ThemeState {
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeState>({ mode: "system", setMode: () => {} });

// The stored preference is an external store: localStorage, shared across tabs.
const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

function readMode(): ThemeMode {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    return stored === "light" || stored === "dark" ? stored : "system";
  } catch {
    return "system";
  }
}

function apply(mode: ThemeMode) {
  const dark = mode === "dark" || (mode === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const mode = useSyncExternalStore(subscribe, readMode, () => "system" as const);

  useEffect(() => {
    apply(mode);
    if (mode !== "system") return;
    const media = matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => apply("system");
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [mode]);

  const setMode = useCallback((next: ThemeMode) => {
    try {
      if (next === "system") localStorage.removeItem(THEME_STORAGE_KEY);
      else localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // Storage unavailable (private mode): fall back to applying it for this page only.
      apply(next);
    }
    listeners.forEach((l) => l());
  }, []);

  return <ThemeContext.Provider value={{ mode, setMode }}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);
