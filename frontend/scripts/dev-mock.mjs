// `npm run dev:mock`: the dev server with the built-in fake API (src/lib/mock.ts).
// A launcher instead of `node --env-file`, because next dev re-spawns Node and
// passes flags through NODE_OPTIONS, which rejects --env-file.
import { spawn } from "node:child_process";
import { createRequire } from "node:module";

const next = createRequire(import.meta.url).resolve("next/dist/bin/next");
const child = spawn(process.execPath, [next, "dev", ...process.argv.slice(2)], {
  stdio: "inherit",
  env: { ...process.env, NEXT_PUBLIC_MOCK: "1" },
});
child.on("exit", (code, signal) => process.exit(signal ? 1 : (code ?? 0)));
