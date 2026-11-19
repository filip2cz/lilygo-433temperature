#!/usr/bin/env python3
"""
Integration tests for the LilyGO 433MHz Weather Gateway HTTP API.
Tests all web endpoints against the live hardware at BOARD_URL
(default: http://192.168.1.50).
"""

import json
import os
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

BOARD_URL = os.environ.get("BOARD_URL", "http://192.168.1.50")


def is_board_online(url: str, timeout: float = 2.0) -> bool:
    """Checks if the LilyGO board web server is reachable."""
    try:
        req = urllib.request.Request(f"{url}/json", headers={"User-Agent": "LilyGOTest/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


BOARD_AVAILABLE = is_board_online(BOARD_URL)


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Custom handler to inspect 302 redirects without following them."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@unittest.skipUnless(BOARD_AVAILABLE, f"Device at {BOARD_URL} is offline or unreachable")
class TestLiveDeviceAPI(unittest.TestCase):

    def setUp(self):
        self.base_url = BOARD_URL

    def _get(self, path: str, follow_redirects: bool = True):
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, headers={"User-Agent": "LilyGOTest/1.0"})
        if not follow_redirects:
            opener = urllib.request.build_opener(NoRedirectHandler)
            try:
                return opener.open(req, timeout=10.0)
            except urllib.error.HTTPError as e:
                return e
        return urllib.request.urlopen(req, timeout=10.0)

    def _post(self, path: str, data: dict, follow_redirects: bool = True):
        url = f"{self.base_url}{path}"
        encoded_data = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(url, data=encoded_data, headers={
            "User-Agent": "LilyGOTest/1.0",
            "Content-Type": "application/x-www-form-urlencoded"
        })
        if not follow_redirects:
            opener = urllib.request.build_opener(NoRedirectHandler)
            try:
                return opener.open(req, timeout=10.0)
            except urllib.error.HTTPError as e:
                return e
        return urllib.request.urlopen(req, timeout=4.0)

    def test_json_endpoint_structure(self):
        """GET /json must return valid JSON with wifi, filter, and repeater objects."""
        resp = self._get("/json")
        self.assertEqual(resp.status, 200)
        self.assertIn("application/json", resp.headers.get("Content-Type", ""))
        body = json.loads(resp.read().decode("utf-8"))

        self.assertIn("wifi", body)
        self.assertIn("is_ap_mode", body["wifi"])
        self.assertIn("ip", body["wifi"])

        self.assertIn("filter", body)
        self.assertIn("enabled", body["filter"])
        self.assertIn("target_model", body["filter"])
        self.assertIn("target_id", body["filter"])
        self.assertIn("target_channel", body["filter"])

        self.assertIn("repeater", body)
        self.assertIn("enabled", body["repeater"])

    def test_root_endpoint(self):
        """GET / and /temp must respond with 200 (number) or 503 (NaN)."""
        for path in ["/", "/temp"]:
            try:
                resp = self._get(path)
                self.assertEqual(resp.status, 200)
                val_str = resp.read().decode("utf-8").strip()
                # Must be convertible to float
                val = float(val_str)
                self.assertIsInstance(val, float)
            except urllib.error.HTTPError as e:
                # 503 is expected if no packet was received since reboot
                self.assertEqual(e.code, 503)
                self.assertIn("NaN", e.read().decode("utf-8"))

    def test_raw_endpoint(self):
        """GET /raw must return text/plain containing packet log."""
        resp = self._get("/raw")
        self.assertEqual(resp.status, 200)
        content_type = resp.headers.get("Content-Type", "")
        self.assertTrue("text/plain" in content_type or "text/html" in content_type)
        body = resp.read().decode("utf-8")
        self.assertIsInstance(body, str)

    def test_debug_page(self):
        """GET /debug must serve HTML monitor with manual filter form and auto-refresh pause script."""
        resp = self._get("/debug")
        self.assertEqual(resp.status, 200)
        html = resp.read().decode("utf-8")
        self.assertIn("433 MHz Monitor", html)
        self.assertIn("Rucni nastaveni filtru", html)
        self.assertIn("name='target_model'", html)
        self.assertIn("name='target_id'", html)
        self.assertIn("name='target_ch'", html)
        self.assertIn("name='filter_enabled'", html)
        self.assertIn("isTyping", html)  # Checks auto-refresh pause JS

    def test_filter_page(self):
        """GET /filter must serve dedicated filter configuration page."""
        resp = self._get("/filter")
        self.assertEqual(resp.status, 200)
        html = resp.read().decode("utf-8")
        self.assertIn("Ruční nastavení filtru 433 MHz", html)
        self.assertIn("name='target_model'", html)
        self.assertIn("name='target_id'", html)
        self.assertIn("name='target_ch'", html)
        self.assertIn("Uložit nastavení filtru", html)

    def test_setup_page(self):
        """GET /setup must serve WiFi configuration form."""
        resp = self._get("/setup")
        self.assertEqual(resp.status, 200)
        html = resp.read().decode("utf-8")
        self.assertIn("Nastavení WiFi", html)
        self.assertIn("name='ssid'", html)
        self.assertIn("name='pass'", html)
        # Background WiFi scan is triggered on /setup; allow it to finish
        time.sleep(1.5)

    def test_set_filter_query_and_redirect(self):
        """GET /set-filter with query params must return 302 and update NVS config."""
        resp = self._get("/set-filter?model=TestModel&id=77&ch=2&enabled=1&redirect=/filter", follow_redirects=False)
        self.assertEqual(resp.status, 302)
        self.assertEqual(resp.headers.get("Location"), "/filter")

        # Verify update via /json
        j_resp = self._get("/json")
        body = json.loads(j_resp.read().decode("utf-8"))
        self.assertEqual(body["filter"]["target_model"], "TestModel")
        self.assertEqual(body["filter"]["target_id"], 77)
        self.assertEqual(body["filter"]["target_channel"], 2)
        self.assertTrue(body["filter"]["enabled"])

    def test_save_filter_post(self):
        """POST /save-filter must save parameters and redirect."""
        post_data = {
            "target_model": "Kedsum-TH",
            "target_id": "186",
            "target_ch": "1",
            "filter_enabled": "1",
            "redirect": "/debug"
        }
        resp = self._post("/save-filter", post_data, follow_redirects=False)
        self.assertEqual(resp.status, 302)
        self.assertEqual(resp.headers.get("Location"), "/debug")

        # Verify update via /json
        j_resp = self._get("/json")
        body = json.loads(j_resp.read().decode("utf-8"))
        self.assertEqual(body["filter"]["target_model"], "Kedsum-TH")
        self.assertEqual(body["filter"]["target_id"], 186)
        self.assertEqual(body["filter"]["target_channel"], 1)

    def test_toggle_filter(self):
        """GET /toggle-filter must flip the enabled flag and redirect."""
        # Get current state
        init_state = json.loads(self._get("/json").read().decode("utf-8"))["filter"]["enabled"]

        # Toggle once
        resp = self._get("/toggle-filter?redirect=/debug", follow_redirects=False)
        self.assertEqual(resp.status, 302)
        state_after = json.loads(self._get("/json").read().decode("utf-8"))["filter"]["enabled"]
        self.assertEqual(state_after, not init_state)

        # Toggle back to restore initial state
        self._get("/toggle-filter?redirect=/debug", follow_redirects=False)
        restored_state = json.loads(self._get("/json").read().decode("utf-8"))["filter"]["enabled"]
        self.assertEqual(restored_state, init_state)


if __name__ == "__main__":
    unittest.main()
