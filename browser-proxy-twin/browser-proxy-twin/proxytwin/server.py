"""One small HTTP server: the directory plus every shop's hosted agent.

Routes (all JSON):
  GET  /health
  POST /cards                      register a card          -> {"id", "card"}
  GET  /cards?category=&area=      discover cards           -> {"cards": [...]}
  GET  /cards/<id>
  POST /agents/<id>/message        send a protocol message to a shop agent
  GET  /owner/<id>/pending         owner inbox (stand-in for WhatsApp)
  POST /owner/<id>/decision        {"hold_id", "accept": true|false}
"""
import argparse
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .directory import Directory
from .schema import CardError
from .shop_agent import AgentError, ShopAgent

MAX_BODY = 64 * 1024


class Hub:
    """Holds the directory and one hosted ShopAgent per registered card."""

    def __init__(self, directory=None, hold_ttl=120):
        self.directory = directory or Directory()
        self.hold_ttl = hold_ttl
        self.agents = {cid: ShopAgent(card, hold_ttl) for cid, card in self.directory.items()}

    def register(self, card):
        card_id, card = self.directory.register(card)
        self.agents[card_id] = ShopAgent(card, self.hold_ttl)
        return card_id, card

    def agent(self, card_id):
        if card_id not in self.agents:
            raise AgentError("NOT_FOUND", f"no such shop {card_id!r}")
        return self.agents[card_id]


class RateLimiter:
    def __init__(self, limit=600, window=60, clock=time.time):
        self.limit, self.window, self.clock = limit, window, clock
        self._hits, self._lock = {}, threading.Lock()

    def allow(self, key):
        now = self.clock()
        with self._lock:
            recent = [t for t in self._hits.get(key, []) if now - t < self.window]
            ok = len(recent) < self.limit
            if ok:
                recent.append(now)
            self._hits[key] = recent
            return ok


class Handler(BaseHTTPRequestHandler):
    hub = None
    limiter = None

    def log_message(self, fmt, *args):
        pass

    def _send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise AgentError("BAD_REQUEST", "request body too large")
        return json.loads(self.rfile.read(length).decode("utf-8") or "{}")

    def _dispatch(self, method):
        try:
            if not self.limiter.allow(self.client_address[0]):
                raise AgentError("RATE_LIMITED", "too many requests, slow down")
            url = urlparse(self.path)
            parts = [p for p in url.path.split("/") if p]
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            hub = self.hub
            if method == "GET" and parts == ["health"]:
                return self._send(200, {"ok": True})
            if method == "POST" and parts == ["cards"]:
                card_id, card = hub.register(self._body())
                return self._send(201, {"id": card_id, "card": card})
            if method == "GET" and parts == ["cards"]:
                return self._send(200, {"cards": hub.directory.search(
                    q.get("category"), q.get("area"), q.get("language"))})
            if method == "GET" and len(parts) == 2 and parts[0] == "cards":
                card = hub.directory.get(parts[1])
                if card is None:
                    raise AgentError("NOT_FOUND", "no such card")
                return self._send(200, {"id": parts[1], **card})
            if method == "POST" and len(parts) == 3 and parts[0] == "agents" and parts[2] == "message":
                return self._send(200, hub.agent(parts[1]).handle(self._body()))
            if method == "GET" and len(parts) == 3 and parts[0] == "owner" and parts[2] == "pending":
                return self._send(200, {"pending": hub.agent(parts[1]).owner_pending()})
            if method == "POST" and len(parts) == 3 and parts[0] == "owner" and parts[2] == "decision":
                body = self._body()
                return self._send(200, hub.agent(parts[1]).owner_decide(
                    body.get("hold_id"), bool(body.get("accept"))))
            raise AgentError("NOT_FOUND", f"no route for {method} {url.path}")
        except AgentError as e:
            self._send(e.status, e.payload())
        except (CardError, json.JSONDecodeError, UnicodeDecodeError) as e:
            self._send(400, {"type": "error", "code": "BAD_REQUEST", "message": str(e)})

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")


def make_server(host="127.0.0.1", port=8080, hub=None, rate_limit=600):
    hub = hub or Hub()
    handler = type("BoundHandler", (Handler,), {"hub": hub, "limiter": RateLimiter(rate_limit)})
    server = ThreadingHTTPServer((host, port), handler)
    server.hub = hub
    return server


def main():
    ap = argparse.ArgumentParser(description="Run the directory and hosted shop agents.")
    ap.add_argument("--host", default=os.environ.get("PTWIN_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PTWIN_PORT", "8080")))
    args = ap.parse_args()
    hub = Hub(Directory(os.environ.get("PTWIN_DATA")), int(os.environ.get("PTWIN_HOLD_TTL", "120")))
    server = make_server(args.host, args.port, hub, int(os.environ.get("PTWIN_RATE_LIMIT", "600")))
    print(f"Browser Proxy Twin server on http://{args.host}:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
