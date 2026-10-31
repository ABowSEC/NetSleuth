import type { PresenceSession } from "@/lib/types";

const DAY_MS = 86_400_000;

interface Segment {
  left: number;
  width: number;
}

/** Online sessions clipped to each of the last `days` local calendar days (oldest first). */
export function presenceByDay(sessions: PresenceSession[], now: Date, days = 7) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const spans = sessions
    .map((s) => ({ start: Date.parse(s.start), end: s.end ? Date.parse(s.end) : now.getTime() }))
    .filter((s) => Number.isFinite(s.start) && Number.isFinite(s.end) && s.end > s.start);

  return Array.from({ length: days }, (_, i) => {
    const dayStart = today - (days - 1 - i) * DAY_MS;
    const dayEnd = dayStart + DAY_MS;
    const segments: Segment[] = [];
    let onlineMs = 0;
    for (const s of spans) {
      const from = Math.max(s.start, dayStart);
      const to = Math.min(s.end, dayEnd, now.getTime());
      if (to <= from) continue;
      onlineMs += to - from;
      segments.push({ left: ((from - dayStart) / DAY_MS) * 100, width: ((to - from) / DAY_MS) * 100 });
    }
    return { dayStart: new Date(dayStart), segments, onlineMs };
  });
}

function hours(ms: number): string {
  const h = ms / 3_600_000;
  if (h < 0.05) return "—";
  return h < 1 ? `${Math.round(h * 60)}m` : `${h.toFixed(h < 10 ? 1 : 0)}h`;
}

export function PresenceStrip({ sessions, now = new Date() }: { sessions: PresenceSession[]; now?: Date }) {
  const rows = presenceByDay(sessions, now);
  return (
    <div className="space-y-1.5">
      {rows.map((row) => (
        <div key={row.dayStart.toISOString()} className="flex items-center gap-3 text-xs">
          <span className="w-9 shrink-0 text-muted">
            {row.dayStart.toLocaleDateString(undefined, { weekday: "short" })}
          </span>
          <div
            className="relative h-3 flex-1 overflow-hidden rounded-sm bg-surface-2"
            role="img"
            aria-label={`${row.dayStart.toLocaleDateString()}: online ${hours(row.onlineMs)}`}
          >
            {row.segments.map((s, i) => (
              <span
                key={i}
                className="absolute inset-y-0 rounded-sm bg-accent"
                style={{ left: `${s.left}%`, width: `max(${s.width}%, 2px)` }}
              />
            ))}
          </div>
          <span className="w-9 shrink-0 text-right tabular-nums text-muted">{hours(row.onlineMs)}</span>
        </div>
      ))}
      <div className="ml-12 mr-12 flex justify-between text-[10px] text-muted" aria-hidden="true">
        <span>12am</span>
        <span>6am</span>
        <span>12pm</span>
        <span>6pm</span>
        <span>12am</span>
      </div>
    </div>
  );
}
