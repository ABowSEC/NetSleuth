// Small shared primitives. Kept in one file: each is a few lines.

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const BUTTON: Record<ButtonVariant, string> = {
  primary: "bg-accent text-bg hover:opacity-85",
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

export function Card({ className = "", ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div {...props} className={`rounded-lg border border-border bg-surface ${className}`} />;
}

/** One quiet line where a list would be. Says what will happen, not that nothing is there. */
export function EmptyLine({ children }: { children: React.ReactNode }) {
  return <p className="px-4 py-6 text-sm text-muted">{children}</p>;
}

/** Small uppercase heading with an optional count, used to split a list into groups. */
export function GroupHeading({ children, count, tone = "text-muted" }: {
  children: React.ReactNode;
  count?: number;
  tone?: string;
}) {
  return (
    <h2 className={`mb-2 flex items-baseline gap-2 text-xs font-semibold uppercase tracking-wider ${tone}`}>
      {children}
      {count !== undefined && <span className="font-mono font-normal tabular-nums">{count}</span>}
    </h2>
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
