#!/usr/bin/env python3
"""Make one bounded request and verify the experiment role and boot ID."""
import argparse
import ipaddress
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    parser.add_argument('--expect-role', default='cloud-probe')
    parser.add_argument('--expect-boot-id')
    parser.add_argument('--timeout', type=float, default=10)
    parser.add_argument('--direct-loopback', action='store_true',
                        help='Bypass proxies only for a numeric loopback address')
    args = parser.parse_args()
    target = urllib.parse.urlsplit(args.url)
    if target.scheme not in ('http', 'https') or not target.hostname:
        parser.error('a valid HTTP/HTTPS URL is required')
    if target.username or target.password or target.query or target.fragment:
        parser.error('use a credential-free URL without a query or fragment')
    if not 0 < args.timeout <= 30:
        parser.error('timeout must be greater than 0 and at most 30 seconds')
    handlers = [NoRedirects()]
    if args.direct_loopback:
        try:
            loopback = ipaddress.ip_address(target.hostname).is_loopback
        except ValueError:
            loopback = False
        if not loopback:
            parser.error('direct-loopback requires a numeric loopback address')
        handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    started = time.monotonic()
    result = {'observed_utc': datetime.now(timezone.utc).isoformat(), 'ok': False}
    try:
        with opener.open(args.url, timeout=args.timeout) as response:
            result['http_status'] = response.status
            body = response.read(65537)
        if len(body) > 65536:
            raise ValueError('health response exceeds 64 KiB')
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError('health response must be a JSON object')
        if payload.get('experiment') != 'work-cloud-private-server':
            raise ValueError('unexpected experiment identity')
        if payload.get('role') != args.expect_role:
            raise ValueError('unexpected service role')
        if not payload.get('boot_id'):
            raise ValueError('missing boot_id')
        if args.expect_boot_id and payload['boot_id'] != args.expect_boot_id:
            raise ValueError('boot_id changed')
        result.update(ok=True, health={key: payload.get(key) for key in
                      ('experiment', 'role', 'boot_id', 'pid', 'utc', 'uptime_seconds')})
    except urllib.error.HTTPError as error:
        result['http_status'] = error.code
        result['error'] = 'HTTP response did not pass health verification'
    except (urllib.error.URLError, OSError, ValueError) as error:
        result['error'] = str(error)
    result['elapsed_seconds'] = round(time.monotonic() - started, 3)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
