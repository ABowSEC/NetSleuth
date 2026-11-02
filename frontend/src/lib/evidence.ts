import type { EvidenceItem } from "./types";

/** Human names for mDNS service types. */
const SERVICES: Record<string, string> = {
  "_googlecast._tcp": "Chromecast",
  "_airplay._tcp": "AirPlay",
  "_raop._tcp": "AirPlay audio",
  "_hap._tcp": "HomeKit",
  "_homekit._tcp": "HomeKit",
  "_matter._tcp": "Matter",
  "_spotify-connect._tcp": "Spotify Connect",
  "_sonos._tcp": "Sonos",
  "_ipp._tcp": "printing",
  "_ipps._tcp": "printing",
  "_printer._tcp": "printing",
  "_pdl-datastream._tcp": "printing",
  "_scanner._tcp": "scanning",
  "_smb._tcp": "file sharing",
  "_rfb._tcp": "screen sharing",
  "_ssh._tcp": "SSH",
  "_companion-link._tcp": "Apple device pairing",
  "_amzn-wplay._tcp": "Fire TV casting",
  "_androidtvremote2._tcp": "Android TV remote",
};

const SOURCE_LABELS: Record<EvidenceItem["source"], string> = {
  upnp: "UPnP",
  roku: "Roku",
  mdns: "mDNS",
  netbios: "NetBIOS",
  rdns: "your router's DNS",
  dhcp: "DHCP",
  ssdp: "SSDP",
  ports: "port check",
};

export interface EvidenceLine {
  text: string;
  via: string;
}

function dhcpClient(value: string): string {
  const android = /android-dhcp-(\d+)/i.exec(value);
  if (android) return `an Android ${android[1]} device`;
  if (/^MSFT/i.test(value)) return "a Windows PC";
  if (/dhcpcd/i.test(value)) return "a Linux device";
  if (/^udhcp/i.test(value)) return "a small embedded device";
  return `"${value}"`;
}

function describe(e: EvidenceItem): string | null {
  const k = e.key;
  const v = e.value;
  switch (e.source) {
    case "upnp":
      if (k === "friendlyName") return `Calls itself "${v}"`;
      if (k === "modelName") return `Describes itself as ${v}`;
      if (k === "manufacturer") return `Made by ${v}`;
      if (k === "modelNumber") return `Model number ${v}`;
      if (k === "deviceType") return `Device type ${v.split(":").slice(-2, -1)[0] ?? v}`;
      return null;
    case "roku":
      return k === "model_name" ? `Describes itself as ${v}` : `Calls itself "${v}"`;
    case "mdns":
      if (k === "txt:fn") return `Calls itself "${v}"`;
      if (k === "txt:md") return `Model ${v}`;
      if (k === "txt:ty" || k === "txt:usb_MDL") return `Printer model ${v}`;
      if (k === "txt:am" || k === "txt:model" || k === "txt:rpMd") return `Apple model identifier ${v}`;
      if (k.startsWith("instance:")) return `Announces itself as "${v}"`;
      return null; // services are grouped into one line by describeEvidence
    case "netbios":
      return `Windows computer name ${v}`;
    case "rdns":
      return `Known to your router as ${v}`;
    case "dhcp":
      if (k === "vendor_class") return `Asked for an address as ${dhcpClient(v)}`;
      return null; // the raw option-55 fingerprint means nothing to people
    case "ssdp":
      return k === "server" ? `Announces software "${v}"` : null;
    case "ports":
      if (k === "open") return `Open ports: ${v.split(",").join(", ")}`;
      if (k === "http_title") return `Has a web page titled "${v}"`;
      return null;
  }
}

/** Plain-language lines explaining how NetSleuth knows what a device is. */
export function describeEvidence(items: EvidenceItem[]): EvidenceLine[] {
  const lines: EvidenceLine[] = [];
  const services = items
    .filter((e) => e.source === "mdns" && e.key.startsWith("service:"))
    .map((e) => SERVICES[e.value])
    .filter((name): name is string => Boolean(name));
  const unique = [...new Set(services)];
  if (unique.length) {
    const list = unique.length > 1 ? `${unique.slice(0, -1).join(", ")} and ${unique.at(-1)}` : unique[0];
    lines.push({ text: `Offers ${list}`, via: SOURCE_LABELS.mdns });
  }
  for (const e of items) {
    const text = describe(e);
    if (text) lines.push({ text, via: SOURCE_LABELS[e.source] });
  }
  return lines;
}
