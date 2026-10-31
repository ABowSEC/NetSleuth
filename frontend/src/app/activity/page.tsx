"use client";

import { useCallback, useMemo, useState } from "react";
import { EventItem } from "@/components/EventItem";
import { Card, EmptyLine, ErrorNotice, GroupHeading } from "@/components/ui";
import { useResource } from "@/hooks/useResource";
import { api } from "@/lib/api";
import { ACTIVITY_FILTERS, groupByDay, type ActivityFilter } from "@/lib/events";

const EMPTY: Record<ActivityFilter, string> = {
  all: "Nothing logged yet. Arrivals, departures and anything odd show up here as they happen.",
  attention: "Nothing needs your attention. New devices, address clashes and scans would show up here.",
  presence: "No arrivals or departures recorded yet.",
  security: "No security alerts. NetSleuth flags address clashes and devices probing others on your network.",
};

export default function ActivityPage() {
  const [filter, setFilter] = useState<ActivityFilter>("all");

  const load = useCallback((signal: AbortSignal) => api.events({ limit: 500 }, signal), []);
  const { data, error, reload } = useResource("events", load, 60_000);

  const test = ACTIVITY_FILTERS.find((f) => f.id === filter)!.test;
  const groups = useMemo(() => groupByDay((data ?? []).filter(test)), [data, test]);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">What happened on your network</h1>
        <a href={api.exportUrl} download className="text-sm text-muted underline decoration-border underline-offset-2 hover:text-text">
          Download log (JSON)
        </a>
      </header>

      <div className="flex flex-wrap gap-x-5 gap-y-2 border-b border-border text-sm" role="tablist" aria-label="Filter the log">
        {ACTIVITY_FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            role="tab"
            aria-selected={filter === f.id}
            onClick={() => setFilter(f.id)}
            className={`-mb-px border-b-2 pb-2 ${
              filter === f.id ? "border-text font-medium text-text" : "border-transparent text-muted hover:text-text"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && <ErrorNotice message={error} onRetry={reload} />}

      {!data && !error ? (
        <p className="py-10 text-sm text-muted" role="status">Loading the log…</p>
      ) : groups.length === 0 ? (
        <EmptyLine>{EMPTY[filter]}</EmptyLine>
      ) : (
        groups.map((group) => (
          <section key={group.label}>
            <GroupHeading count={group.events.length}>{group.label}</GroupHeading>
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
