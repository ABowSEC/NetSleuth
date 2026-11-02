"use client";

import { useCallback, useState } from "react";
import { useLive } from "@/context/LiveContext";
import { useToast } from "@/context/ToastContext";
import { api } from "@/lib/api";

/** Start/stop Identify mode from anywhere; status comes from the live connection. */
export function useIdentify() {
  const { identify, setIdentify } = useLive();
  const toast = useToast();
  const [pending, setPending] = useState(false);

  const start = useCallback(async (macs?: string[]) => {
    setPending(true);
    try {
      setIdentify(await api.startIdentify(macs ? { macs } : {}));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't start Identify mode.");
    } finally {
      setPending(false);
    }
  }, [setIdentify, toast]);

  const stop = useCallback(async () => {
    setPending(true);
    try {
      setIdentify(await api.stopIdentify());
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't stop Identify mode.");
    } finally {
      setPending(false);
    }
  }, [setIdentify, toast]);

  return { status: identify, pending, start, stop };
}
