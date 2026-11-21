"""Exercise only the launcher, with fake X11/Chromium processes and isolated profiles.

Run: python tests/kiosk_launcher_test.py
No display, network, PostgreSQL, real browser, or kiosk profile is used.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]


class KioskLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="progressive-kiosk-test-")
        self.directory = Path(self.temp.name)
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        for name in ("numlockx", "xset"):
            path = self.bin / name
            path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o755)
        chromium = self.bin / "chromium"
        chromium.write_text("""#!/usr/bin/env python3
import json, os, signal, sys, time
with open(os.environ['KIOSK_TEST_LOG'], 'a') as log:
    log.write(json.dumps({'pid': os.getpid(), 'args': sys.argv[1:]}) + '\\n')
def stop(*_):
    sys.exit(0)
signal.signal(signal.SIGTERM, stop)
while True:
    time.sleep(0.05)
""")
        chromium.chmod(0o755)
        self.log = self.directory / "browser.jsonl"
        self.env = {
            **os.environ,
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            "PROGRESSIVE_URL": "https://progressive.example.invalid/table/test",
            "PROGRESSIVE_PROFILE_DIR": str(self.directory / "profile"),
            "KIOSK_TEST_LOG": str(self.log),
        }
        self.processes = []

    def tearDown(self):
        # Only process groups created by this test; never a real kiosk/browser.
        for process in self.processes:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for process in self.processes:
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=2)
            if process.stderr:
                process.stderr.close()
        self.temp.cleanup()

    def start(self, **changes):
        process = subprocess.Popen(
            ["sh", str(ROOT / "scripts/kiosk.sh")],
            env={**self.env, **changes},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        self.processes.append(process)
        return process

    def launches(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def wait_until(self, predicate, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.03)
        self.fail("Timed out waiting for launcher state")

    @staticmethod
    def running(pid):
        try:
            # A terminated but not yet reaped child is no longer running.
            return Path(f"/proc/{pid}/stat").read_text().split()[2] != "Z"
        except FileNotFoundError:
            return False

    def test_duplicate_autostart_has_one_browser(self):
        first = self.start()
        self.wait_until(lambda: len(self.launches()) == 1)
        duplicate = self.start()
        self.wait_until(lambda: duplicate.poll() is not None)
        self.assertEqual(duplicate.returncode, 0)
        self.assertIsNone(first.poll())
        self.assertEqual(len(self.launches()), 1)
        self.assertIn("already running", duplicate.stderr.read())

    def test_browser_exit_restarts_and_stop_cleans_owned_browser(self):
        launcher = self.start()
        self.wait_until(lambda: len(self.launches()) == 1)
        first = self.launches()[0]["pid"]
        os.kill(first, signal.SIGTERM)
        self.wait_until(lambda: len(self.launches()) == 2)
        replacement = self.launches()[1]["pid"]
        self.assertNotEqual(first, replacement)
        launcher.terminate()
        self.assertEqual(launcher.wait(timeout=3), 0)
        self.wait_until(lambda: not self.running(replacement))
        # A stopped launcher releases its profile lock for the next session.
        self.start()
        self.wait_until(lambda: len(self.launches()) == 3)

    def test_profile_lock_does_not_stop_another_profile(self):
        first = self.start()
        self.wait_until(lambda: len(self.launches()) == 1)
        other = self.start(PROGRESSIVE_PROFILE_DIR=str(self.directory / "other"))
        self.wait_until(lambda: len(self.launches()) == 2)
        other_browser = self.launches()[1]["pid"]
        first.terminate()
        self.assertEqual(first.wait(timeout=3), 0)
        self.assertIsNone(other.poll())
        self.assertTrue(self.running(other_browser))
        self.assertIn("--user-data-dir=" + str(self.directory / "other"), self.launches()[1]["args"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
