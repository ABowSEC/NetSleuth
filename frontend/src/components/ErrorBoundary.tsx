"use client";

import { Component } from "react";

interface State {
  error: Error | null;
}

/** Keeps a rendering bug in one view from blanking the whole dashboard. */
export class ErrorBoundary extends Component<{ children: React.ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error("NetSleuth UI error:", error);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div role="alert" className="mx-auto max-w-lg px-4 py-20 text-center">
        <p className="text-lg font-semibold">This page hit a bug and stopped drawing.</p>
        <p className="mt-2 text-sm text-muted">
          Monitoring isn&apos;t affected. The error was: <code className="font-mono">{this.state.error.message}</code>
        </p>
        <button
          type="button"
          onClick={() => this.setState({ error: null })}
          className="mt-6 rounded-md border border-border bg-surface px-4 py-2 text-sm font-medium hover:bg-surface-2"
        >
          Try again
        </button>
      </div>
    );
  }
}
