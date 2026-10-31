// Small shared primitives. Kept in one file: each is a few lines.

import type { Severity } from "@/lib/types";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const BUTTON: Record<ButtonVariant, string> = {
  primary: "bg-accent text-white dark:text-bg hover:opacity-90",
  secondary: "border border-border bg-surface text-text hover:bg-surface-2",
  ghost: "text-muted hover:bg-surface-2 hover:text-text",
  danger: "border border-danger/40 text-danger hover:bg-danger/10",
};

export function Button({
  variant = "secondary",
  size = "md",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: "sm" | "md" }) {
  return (
    <button
      type="button"
      {...props}
      className={`inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 ${
        size === "sm" ? "h-8 px-2.5 text-xs" : "h-9 px-3.5 text-sm"
      } ${BUTTON[variant]} ${className}`}
    />
  );
}

export function StatusDot({ online, className = "" }: { online: boolean; className?: string }) {
  return (
    <span
      className={`inline-block size-2 shrink-0 rounded-full ${online ? "bg-ok" : "bg-muted/40"} ${className}`}
      aria-label={online ? "Online" : "Offline"}
      role="img"
    />
  );
}

const SEVERITY_STYLE: Record<Severity, string> = {
  info: "text-muted",
  low: "text-info",
  medium: "text-warn",
  high: "text-danger",
  critical: "text-surface bg-danger",
};

export function SeverityTag({ severity }: { severity: Severity }) {
  if (severity === "info") return null;
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${SEVERITY_STYLE[severity]} ${
        severity === "critical" ? "" : "bg-surface-2"
      }`}
    >
      {severity}
    </span>
  );
}

export function Card({ className = "", ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div {...props} className={`rounded-xl border border-border bg-surface ${className}`} />;
}

export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="px-6 py-14 text-center">
      <p className="font-medium">{title}</p>
      {children && <div className="mt-1 text-sm text-muted">{children}</div>}
    </div>
  );
}

export function ErrorNotice({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm">
      <span className="flex-1 text-danger">{message}</span>
      {onRetry && <Button size="sm" onClick={onRetry}>Try again</Button>}
    </div>
  );
}
