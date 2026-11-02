import { expect, it } from "vitest";
import { describeEvidence } from "./evidence";
import type { EvidenceItem } from "./types";

const e = (source: EvidenceItem["source"], key: string, value: string): EvidenceItem =>
  ({ source, key, value, confidence: 1, last_seen: "2026-10-31T00:00:00Z" });

it("turns clues into sentences with where they came from", () => {
  const lines = describeEvidence([
    e("upnp", "friendlyName", "Bedroom Roku"),
    e("upnp", "modelName", "Roku Ultra"),
    e("dhcp", "vendor_class", "android-dhcp-14"),
    e("netbios", "name", "DESKTOP-4FJ2K9Q"),
    e("rdns", "name", "den-pc.lan"),
    e("ports", "open", "80,9100"),
  ]);
  expect(lines).toEqual([
    { text: 'Calls itself "Bedroom Roku"', via: "UPnP" },
    { text: "Describes itself as Roku Ultra", via: "UPnP" },
    { text: "Asked for an address as an Android 14 device", via: "DHCP" },
    { text: "Windows computer name DESKTOP-4FJ2K9Q", via: "NetBIOS" },
    { text: "Known to your router as den-pc.lan", via: "your router's DNS" },
    { text: "Open ports: 80, 9100", via: "port check" },
  ]);
});

it("groups mDNS services into one readable line", () => {
  const lines = describeEvidence([
    e("mdns", "service:_googlecast._tcp", "_googlecast._tcp"),
    e("mdns", "service:_spotify-connect._tcp", "_spotify-connect._tcp"),
    e("mdns", "service:_ipp._tcp", "_ipp._tcp"),
    e("mdns", "service:_ipps._tcp", "_ipps._tcp"),
    e("mdns", "service:_mystery._tcp", "_mystery._tcp"),
  ]);
  expect(lines[0]).toEqual({ text: "Offers Chromecast, Spotify Connect and printing", via: "mDNS" });
  expect(lines).toHaveLength(1);
});

it("hides clues that mean nothing to people", () => {
  expect(describeEvidence([
    e("dhcp", "params", "1,3,6,15"),
    e("ssdp", "location", "http://192.168.1.30:8060/"),
  ])).toEqual([]);
});

it("explains Windows and unrecognised DHCP clients", () => {
  expect(describeEvidence([e("dhcp", "vendor_class", "MSFT 5.0")])[0].text).toBe("Asked for an address as a Windows PC");
  expect(describeEvidence([e("dhcp", "vendor_class", "acme-os 2")])[0].text).toBe('Asked for an address as "acme-os 2"');
});
