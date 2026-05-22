export type Severity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
export type DeviceType = "apple" | "router" | "tv" | "dns" | "gaming" | "other"
export type SortKey = "label" | "type" | "ip" | "mac" | "connections" | "dns" | "last_seen"
export type Filter = DeviceType | "all"
export type Theme = "light" | "dark" | "system"

export interface Device {
  hostname: string
  mac: string
  dns_queries: string[]
  connections: string[]
  services: string[]
  last_seen: string
  connection_count: number
  dns_count: number
}

export interface Alert {
  timestamp: string
  message: string
  type: string
  severity: Severity
}

export interface NetworkData {
  devices: Record<string, Device>
  last_update: string | null
  total_devices: number
  total_connections: number
  total_dns_queries: number
  alerts: Alert[]
}

export interface TrendPoint {
  t: number
  devices: number
  connections: number
  dns: number
  alerts: number
}

export interface SuspiciousDevice {
  ip: string
  score: number | null
  level: Severity | "NORMAL"
  total_anomalies: number
  recent_anomalies: [string, number][]
  last_seen: string | null
}

export interface AnomalyEvent {
  timestamp: string
  src_ip: string
  dst_ip: string
  src_port: number
  dst_port: number
  protocol: string
  score: number
  extra: Record<string, unknown>
}
