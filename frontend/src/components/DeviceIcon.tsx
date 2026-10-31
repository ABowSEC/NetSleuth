import type { DeviceType } from "@/lib/types";

// 24x24 stroke icons, drawn to read clearly at 20px.
const PATHS: Record<DeviceType, React.ReactNode> = {
  router: (
    <>
      <rect x="3" y="13" width="18" height="7" rx="2" />
      <path d="M7 16.5h.01M11 16.5h.01M8 13l-2-6M16 13l2-6" />
      <path d="M9.5 6.5a4 4 0 0 1 5 0" />
    </>
  ),
  computer: (
    <>
      <rect x="4" y="4" width="16" height="11" rx="1.5" />
      <path d="M2 19h20M9 15v4M15 15v4" />
    </>
  ),
  phone: (
    <>
      <rect x="7" y="2.5" width="10" height="19" rx="2" />
      <path d="M11 18.5h2" />
    </>
  ),
  tablet: (
    <>
      <rect x="4.5" y="2.5" width="15" height="19" rx="2" />
      <path d="M11 18.5h2" />
    </>
  ),
  tv: (
    <>
      <rect x="2.5" y="4.5" width="19" height="12" rx="1.5" />
      <path d="M8 20.5h8M12 16.5v4" />
    </>
  ),
  speaker: (
    <>
      <rect x="6" y="2.5" width="12" height="19" rx="2" />
      <circle cx="12" cy="14" r="3.5" />
      <path d="M12 6.5h.01" />
    </>
  ),
  camera: (
    <>
      <circle cx="12" cy="11" r="7" />
      <circle cx="12" cy="11" r="2.5" />
      <path d="M8 20.5h8" />
    </>
  ),
  printer: (
    <>
      <path d="M7 9V3.5h10V9" />
      <rect x="3" y="9" width="18" height="8" rx="1.5" />
      <path d="M7 14h10v6.5H7z" />
    </>
  ),
  console: (
    <>
      <path d="M6.5 7.5h11a4 4 0 0 1 3.9 4.9l-1 4.3a2.4 2.4 0 0 1-4.1 1L14.4 15.5H9.6l-1.9 2.2a2.4 2.4 0 0 1-4.1-1l-1-4.3a4 4 0 0 1 3.9-4.9Z" />
      <path d="M8 10.5v3M6.5 12h3M15.5 11.5h.01M17.5 13h.01" />
    </>
  ),
  iot: (
    <>
      <path d="M9 18h6M10 21h4" />
      <path d="M12 3a6 6 0 0 0-3.5 10.9c.6.4 1 1.1 1 1.8V16h5v-.3c0-.7.4-1.4 1-1.8A6 6 0 0 0 12 3Z" />
    </>
  ),
  unknown: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.5 9.5a2.5 2.5 0 1 1 3.4 2.3c-.6.3-.9.8-.9 1.4v.3M12 16.8h.01" />
    </>
  ),
};

export function DeviceIcon({ type, className = "size-5" }: { type: DeviceType; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {PATHS[type] ?? PATHS.unknown}
    </svg>
  );
}
