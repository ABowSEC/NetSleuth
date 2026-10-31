"""Stand-in for `python -m netsleuth` that speaks just enough of the contract.

Behaviour comes from FAKE_MODE:
  ok     serve /api/v1/health; exit 0 when stdin closes (writes FAKE_MARKER)
  die    serve health briefly, then crash with exit code 1
  exitN  exit immediately with code N (e.g. exit3)
  hang   serve health and ignore stdin closing (must be killed)
  slow   wait FAKE_DELAY seconds before serving health
"""
import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

mode = os.environ.get("FAKE_MODE", "ok")
if mode.startswith("exit"):
    sys.exit(int(mode[4:]))

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, required=True)
args = parser.parse_args()

if mode == "slow":
    time.sleep(float(os.environ.get("FAKE_DELAY", "1")))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/v1/health":
            body = json.dumps({"status": "ok", "version": "fake", "capturing": True, "interface": "eth0"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()

if mode == "die":
    time.sleep(0.6)
    os._exit(1)
if mode == "hang":
    while True:
        time.sleep(1)

while sys.stdin.buffer.read(1024):
    pass
marker = os.environ.get("FAKE_MARKER")
if marker:
    Path(marker).write_text("clean", encoding="utf-8")
sys.exit(0)
