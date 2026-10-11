from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def build_handler() -> type[BaseHTTPRequestHandler]:
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/health":
                self.send_error(404)
                return
            body = json.dumps({"service": "contract-workflow-reference", "status": "OK", "mode": "offline-mock"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return HealthHandler


def serve(host: str = "127.0.0.1", port: int = 8240) -> None:
    ThreadingHTTPServer((host, port), build_handler()).serve_forever()


if __name__ == "__main__":
    serve()
