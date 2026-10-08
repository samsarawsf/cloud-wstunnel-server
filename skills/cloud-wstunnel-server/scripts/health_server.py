#!/usr/bin/env python3
"""Loopback-only, fixed-response health service for a tunnel experiment."""
import argparse
import json
import os
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=19084)
    parser.add_argument('--role', default='cloud-probe')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be 1..65535')
    boot_id, started = uuid.uuid4().hex, time.monotonic()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != '/health':
                self.send_error(404)
                return
            body = json.dumps({
                'experiment': 'work-cloud-private-server',
                'role': args.role, 'boot_id': boot_id, 'pid': os.getpid(),
                'utc': datetime.now(timezone.utc).isoformat(),
                'uptime_seconds': round(time.monotonic() - started, 3),
            }).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(('127.0.0.1', args.port), Handler) as server:
        print(json.dumps({'pid': os.getpid(), 'boot_id': boot_id,
                          'bind': '127.0.0.1:' + str(args.port)}), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
