from __future__ import annotations

import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread
import unittest

from contract_workflow.app import build_handler


class HealthTests(unittest.TestCase):
    def test_health_endpoint(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler())
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = HTTPConnection("127.0.0.1", server.server_port)
            connection.request("GET", "/health")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read()), {"service": "contract-workflow-reference", "status": "OK", "mode": "offline-mock"})
        finally:
            server.shutdown()
            server.server_close()
