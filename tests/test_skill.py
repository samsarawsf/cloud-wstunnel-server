import importlib.util
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/cloud-wstunnel-server'


class SkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as candidate:
            candidate.bind(('127.0.0.1', 0))
            cls.port = candidate.getsockname()[1]
        cls.url = 'http://127.0.0.1:%d/health' % cls.port
        cls.service = subprocess.Popen(
            [sys.executable, str(SKILL / 'scripts/health_server.py'), '--port', str(cls.port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        cls.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for _ in range(60):
            try:
                with cls.opener.open(cls.url, timeout=1) as response:
                    cls.health = json.load(response)
                return
            except OSError:
                if cls.service.poll() is not None:
                    raise RuntimeError(cls.service.stderr.read())
                time.sleep(0.05)
        cls.service.terminate()
        cls.service.wait(timeout=5)
        raise RuntimeError('Temporary loopback health service did not start')

    @classmethod
    def tearDownClass(cls):
        cls.service.terminate()
        cls.service.wait(timeout=5)
        cls.service.stderr.close()

    def probe(self, *extra):
        return subprocess.run(
            [sys.executable, str(SKILL / 'scripts/probe.py'), self.url,
             '--direct-loopback', *extra], capture_output=True, text=True)

    def test_actual_health_and_same_boot(self):
        self.assertEqual(self.health['pid'], self.service.pid)
        self.assertEqual(self.health['role'], 'cloud-probe')
        result = self.probe('--expect-boot-id', self.health['boot_id'])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['health']['boot_id'], self.health['boot_id'])

    def test_changed_process_is_rejected(self):
        result = self.probe('--expect-boot-id', 'different-process')
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)['ok'])

    def test_wrong_role_is_rejected(self):
        result = self.probe('--expect-role', 'wrong-service')
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)['ok'])

    def test_unknown_path_is_not_a_file_server(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.opener.open(self.url.replace('/health', '/etc/passwd'), timeout=1)
        self.assertEqual(error.exception.code, 404)

    def test_proxy_exception_cannot_target_remote(self):
        result = subprocess.run(
            [sys.executable, str(SKILL / 'scripts/probe.py'),
             'http://192.0.2.1/health', '--direct-loopback'],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('numeric loopback', result.stderr)

    def test_redirect_exception_cannot_escape_loopback(self):
        spec = importlib.util.spec_from_file_location('probe', SKILL / 'scripts/probe.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        redirected = module.NoRedirects().redirect_request(
            urllib.request.Request(self.url), None, 302, 'redirect', {},
            'http://192.0.2.1/')
        self.assertIsNone(redirected)

    def test_credentials_are_rejected_in_probe_url(self):
        result = subprocess.run(
            [sys.executable, str(SKILL / 'scripts/probe.py'),
             'http://user:password@127.0.0.1:%d/health' % self.port],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('credential-free', result.stderr)

    def test_document_links_and_skill_metadata(self):
        for path in ROOT.rglob('*.md'):
            if '.git' in path.parts:
                continue
            for reference in re.findall(r'\]\(([^)]+)\)', path.read_text()):
                if reference.startswith(('http://', 'https://', '#')):
                    continue
                self.assertTrue((path.parent / reference.split('#')[0]).exists(),
                                '%s -> %s' % (path, reference))
        text = (SKILL / 'SKILL.md').read_text()
        self.assertTrue(text.startswith('---\n'))
        self.assertIn('name: cloud-wstunnel-server\n', text)
        self.assertIn('description:', text)
        self.assertIn('$cloud-wstunnel-server', (SKILL / 'agents/openai.yaml').read_text())


if __name__ == '__main__':
    unittest.main()
