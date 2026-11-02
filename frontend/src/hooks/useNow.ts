"use client";

import { useSyncExternalStore } from "react";

/**
 * The current time, rounded down to ``stepMs`` so renders stay pure and the
 * value only changes (and re-renders) once per step.
 */
export function useNow(stepMs = 15_000): number {
  return useSyncExternalStore(
    (onChange) => {
      const timer = setInterval(onChange, stepMs);
      return () => clearInterval(timer);
    },
    () => Math.floor(Date.now() / stepMs) * stepMs,
    () => 0,
  );
}
