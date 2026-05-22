import type { DeviceType, Severity } from "./types"

export function getDeviceType(hostname: string): DeviceType {
  const h = (hostname || "").toLowerCase()
  if (h.includes("apple") || h.includes("iphone") || h.includes("ipad") ||
      h.includes("macbook") || h.includes("airpods") || h.includes("homepod")) return "apple"
  if (h.includes("router") || h.includes("gateway") || h.includes("linksys") ||
      h.includes("netgear") || h.includes("access point")) return "router"
  if (h.includes("smart tv") || h.includes(" tv") || h.includes("roku") ||
      h.includes("lg tv") || h.includes("samsung tv") || h.includes("fire tv") ||
      h.includes("chromecast")) return "tv"
  if (h.includes("dns server") || h.includes("pihole") || h.includes("dns")) return "dns"
  if (h.includes("xbox") || h.includes("playstation") || h.includes("nintendo") ||
      h.includes("steam deck")) return "gaming"
  return "other"
}

export const TYPE_LABELS: Record<DeviceType, string> = {
  apple: "Apple", router: "Router", tv: "TV",
  dns: "DNS", gaming: "Gaming", other: "Other",
}

export const TYPE_COLORS: Record<DeviceType, string> = {
  apple:  "bg-green-100 text-green-800",
  router: "bg-blue-100 text-blue-800",
  tv:     "bg-orange-100 text-orange-800",
  dns:    "bg-purple-100 text-purple-800",
  gaming: "bg-red-100 text-red-800",
  other:  "bg-gray-100 text-gray-600",
}

export const SEVERITY_COLORS: Record<Severity, string> = {
  LOW:      "border-blue-400 bg-blue-50 text-blue-800",
  MEDIUM:   "border-yellow-400 bg-yellow-50 text-yellow-800",
  HIGH:     "border-red-400 bg-red-50 text-red-800",
  CRITICAL: "border-purple-500 bg-purple-50 text-purple-800",
}

export const SEVERITY_BADGE: Record<Severity | "NORMAL", string> = {
  NORMAL:   "bg-gray-100 text-gray-500",
  LOW:      "bg-blue-100 text-blue-700",
  MEDIUM:   "bg-yellow-100 text-yellow-700",
  HIGH:     "bg-red-100 text-red-700",
  CRITICAL: "bg-purple-100 text-purple-800",
}

export const FILTERS = ["all", "apple", "router", "tv", "dns", "gaming", "other"] as const

export function formatRelativeTime(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime()
    if (diff < 60_000)  return "just now"
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
    return `${Math.floor(diff / 86_400_000)}d ago`
  } catch {
    return iso
  }
}
