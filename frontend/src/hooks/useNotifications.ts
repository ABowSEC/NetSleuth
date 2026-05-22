"use client"
import { useState, useEffect } from "react"

export function useNotifications() {
  const [permission, setPermission] = useState<NotificationPermission>("default")

  useEffect(() => {
    if ("Notification" in window) setPermission(Notification.permission)
  }, [])

  const requestPermission = async () => {
    if (!("Notification" in window)) return
    const p = await Notification.requestPermission()
    setPermission(p)
  }

  return { permission, requestPermission }
}
