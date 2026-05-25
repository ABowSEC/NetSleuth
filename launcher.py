import os
import sys
import socket
import subprocess
import psutil

ROOT = os.path.dirname(os.path.abspath(__file__))

CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def c(text, code):
    return f"{code}{text}{RESET}"


def get_interfaces():
    addrs = psutil.net_if_addrs()
    result = []
    for name, stats in psutil.net_if_stats().items():
        if stats.isup and not name.lower().startswith("lo"):
            ip = "N/A"
            for addr in addrs.get(name, []):
                if addr.family == socket.AF_INET:
                    ip = addr.address
                    break
            result.append((name, ip))
    return sorted(result)


def pick(prompt, options):
    for i, opt in enumerate(options, 1):
        print(f"    {i}) {opt}")
    while True:
        try:
            raw = input(f"\n  {prompt}: ").strip()
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return idx
        except (ValueError, KeyboardInterrupt):
            pass
        print(f"  {c('Invalid selection, try again.', YELLOW)}")


def open_window(title, cwd, args):
    """Open a new cmd window with a title."""
    subprocess.Popen(
        ["cmd", "/k", f"title {title}&&"] + args,
        cwd=cwd,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )


def main():
    os.system("cls")
    print()
    print(c("  NetSleuth", CYAN + BOLD))
    print("  " + "─" * 38)
    print()

    modes = [
        "Start  (monitor traffic)",
        "Train  (capture data + build model)",
    ]
    print(c("  Select mode:", BOLD))
    mode_idx = pick("Mode", modes)
    print()

    # ── Train ────────────────────────────────────────────────────────────────
    if mode_idx == 1:
        print(c("  Capturing 5 minutes of normal traffic...", YELLOW))
        print()
        backend = os.path.join(ROOT, "backend")
        r = subprocess.run([sys.executable, "-m", "src.ml.capture_training"], cwd=backend)
        if r.returncode != 0:
            print(c("\n  [!] Capture failed — aborting.", RED))
            input("\n  Press Enter to exit...")
            sys.exit(1)
        print()
        print(c("  Training model...", YELLOW))
        r = subprocess.run([sys.executable, "-m", "src.ml.train_model"], cwd=backend)
        if r.returncode == 0:
            print(c("\n  Model saved to backend/models/isoforest.pkl", GREEN))
        else:
            print(c("\n  [!] Training failed.", RED))
        input("\n  Press Enter to exit...")
        return

    # ── Start ────────────────────────────────────────────────────────────────
    interfaces = get_interfaces()
    if not interfaces:
        print(c("  [!] No active interfaces found.", RED))
        input("  Press Enter to exit...")
        sys.exit(1)

    if len(interfaces) == 1:
        selected, ip = interfaces[0]
        print(c(f"  Auto-selected interface: {selected} ({ip})", YELLOW))
    else:
        print(c("  Select interface:", BOLD))
        labels = [f"{name}  ({ip})" for name, ip in interfaces]
        idx = pick("Interface", labels)
        selected, ip = interfaces[idx]

    print()
    print(c(f"  Starting on {selected}...", GREEN))
    print(f"  Backend  -> http://localhost:5000")
    print(f"  Frontend -> http://localhost:3000")
    print()

    open_window(
        "NetSleuth Backend",
        os.path.join(ROOT, "backend"),
        [sys.executable, "agent.py", "--web", "--interface", selected],
    )
    open_window(
        "NetSleuth Frontend",
        os.path.join(ROOT, "frontend"),
        ["npm", "run", "dev"],
    )


if __name__ == "__main__":
    main()
