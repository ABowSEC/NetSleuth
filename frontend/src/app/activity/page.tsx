"use client";

import { useCallback, useMemo, useState } from "react";
import { EventItem, KIND_LABELS } from "@/components/EventItem";
import { Card, EmptyState, ErrorNotice } from "@/components/ui";
import { useResource } from "@/hooks/useResource";
import { api } from "@/lib/api";
import { groupByDay, isImportant } from "@/lib/events";
import { EVENT_KINDS, type EventKind } from "@/lib/types";

type KindFilter = EventKind | "important";

export default function ActivityPage() {
  const [filter, setFilter] = useState<KindFilter | null>(null);
  const kind = filter && filter !== "important" ? filter : undefined;

  const load = useCallback((signal: AbortSignal) => api.events({ limit: 300, kind }, signal), [kind]);
  const { data, error, loading, reload } = useResource(`events:${kind ?? "all"}`, load, 60_000);

  const events = useMemo(
    () => (filter === "important" ? (data ?? []).filter(isImportant) : data ?? []),
    [data, filter],
  );
  const groups = useMemo(() => groupByDay(events), [events]);

  const chips: { id: KindFilter | null; label: string }[] = [
    { id: null, label: "Everything" },
    { id: "important", label: "Needs attention" },
    ...EVENT_KINDS.map((k) => ({ id: k, label: KIND_LABELS[k] })),
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Activity</h1>
          <p className="mt-1 text-sm text-muted">Arrivals, departures and anything that looked wrong.</p>
        </div>
        <a href={api.exportUrl} download className="text-sm font-medium text-accent hover:underline">
          Export as JSON
        </a>
      </div>

      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter activity">
        {chips.map((c) => (
          <button
            key={c.label}
            type="button"
            aria-pressed={filter === c.id}
            onClick={() => setFilter(c.id)}
            className={`rounded-full border px-3 py-1 text-sm ${
              filter === c.id ? "border-accent bg-accent-soft text-accent" : "border-border text-muted hover:text-text"
            }`}
          >
            {c.label}
          </button>
        ))}
      </div>

      {error && <ErrorNotice message={error} onRetry={reload} />}

      {loading && !data ? (
        <Card className="h-64 animate-pulse" aria-hidden="true" />
      ) : groups.length === 0 ? (
        <Card>
          <EmptyState title="Nothing here yet">
            {filter ? "No events match this filter." : "Events appear as devices join, leave or change."}
          </EmptyState>
        </Card>
      ) : (
        groups.map((group) => (
          <section key={group.label}>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{group.label}</h2>
            <Card>
              <ul className="divide-y divide-border">
                {group.events.map((e) => <EventItem key={e.id} event={e} />)}
              </ul>
            </Card>
          </section>
        ))
      )}
    </div>
  );
}
