import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

// Production: a static export in out/, served by the NetSleuth backend itself.
// Development: `next dev` proxies /api to a running backend (start it with --dev
// so it accepts writes from localhost:3000). Rewrites can't be combined with a
// static export, so they only exist in the dev phase.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:5000";

export default function config(phase: string): NextConfig {
  if (phase === PHASE_DEVELOPMENT_SERVER) {
    return {
      async rewrites() {
        return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
      },
    };
  }
  return { output: "export" };
}
