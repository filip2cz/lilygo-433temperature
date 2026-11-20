#!/usr/bin/env python3
"""
Lightweight software simulator / mock server for the LilyGO 433MHz Weather Gateway.
Simulates all ESP32 web server endpoints and NVS state transitions:
- GET / and GET /temp
- GET /json
- GET /raw
- GET /debug (HTML dashboard with manual filter form and auto-refresh pause)
- GET /filter (dedicated filter page)
- GET /setup (WiFi and IP setup)
- POST /save-filter and GET /set-filter (filter configuration with 302 redirects)
- GET /toggle-filter (filter enable toggle with 302 redirect)
- GET /repeat and GET /tx (repeater trigger)

Can be run standalone for local web UI testing:
    python3 tests/mock_server.py [port]
"""

import http.server
import json
import sys
import urllib.parse

DEFAULT_PORT = 8080


class GatewayState:
    def __init__(self):
        self.temperature = 9.1
        self.humidity = 81
        self.last_model = "Hideki-TS04"
        self.last_id = 12
        self.last_channel = 1
        self.last_battery_ok = 1
        self.filter_enabled = True
        self.filter_model = "Hideki-TS04"
        self.filter_id = 12
        self.filter_channel = 1
        self.wifi_ssid = "Simulated-WiFi"
        self.wifi_ip = "127.0.0.1"
        self.is_ap_mode = False
        self.use_static_ip = False
        self.repeater_enabled = False
        self.tx_count = 0
        self.debug_log = [
            {
                "time_s": 5,
                "model": "Hideki-TS04",
                "id": 12,
                "channel": 1,
                "temp": 9.1,
                "humidity": 81,
                "battery": "OK",
                "accepted": True,
                "raw": '{"model":"Hideki-TS04","id":12,"channel":1,"battery_ok":1,"temperature_C":9.1,"humidity":81}',
            },
            {
                "time_s": 35,
                "model": "Kedsum-TH",
                "id": 186,
                "channel": 1,
                "temp": 21.4,
                "humidity": 55,
                "battery": "OK",
                "accepted": False,
                "raw": '{"model":"Kedsum-TH","id":186,"channel":1,"battery_ok":1,"temperature_C":21.4,"humidity":55}',
            },
        ]


class GatewayMockHandler(http.server.BaseHTTPRequestHandler):
    state = GatewayState()

    def log_message(self, format, *args):
        # Silent by default unless verbose
        pass

    def _send_html(self, content: str, status: int = 200):
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, content: str, status: int = 200):
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data: dict, status: int = 200):
        body = (json.dumps(data) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/temp"):
            if self.state.temperature is None:
                self._send_text("NaN\n", status=503)
            else:
                self._send_text(f"{self.state.temperature:.1f}\n")

        elif path == "/json":
            payload = {
                "temperature": self.state.temperature,
                "humidity": self.state.humidity,
                "model": self.state.last_model,
                "id": self.state.last_id,
                "channel": self.state.last_channel,
                "battery_ok": self.state.last_battery_ok,
                "updated_s_ago": 5,
                "wifi": {
                    "is_ap_mode": self.state.is_ap_mode,
                    "ssid": self.state.wifi_ssid,
                    "ip": self.state.wifi_ip,
                    "static_ip": self.state.use_static_ip,
                },
                "repeater": {
                    "enabled": self.state.repeater_enabled,
                },
                "filter": {
                    "enabled": self.state.filter_enabled,
                    "target_model": self.state.filter_model,
                    "target_id": self.state.filter_id,
                    "target_channel": self.state.filter_channel,
                },
            }
            self._send_json(payload)

        elif path == "/raw":
            lines = [f"[{e['time_s']}s zpet] [{'OK' if e['accepted'] else 'IGN'}] {e['raw']}" for e in self.state.debug_log]
            self._send_text("\n".join(lines) + "\n")

        elif path == "/debug":
            status_text = "ZAPNUT" if self.state.filter_enabled else "VYPNUT"
            html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>LilyGO 433MHz - Zachycene signaly (SIMULATOR)</title></head><body>
<h1>433 MHz Monitor - Zachycene signaly (SIMULATOR)</h1>
<div class='filter-info'><b>Aktivni filtr:</b> {status_text} | Cil: <code>{self.state.filter_model}</code></div>
<div class='filter-form-box'>
<b>Rucni nastaveni filtru senzoru</b>
<form method='POST' action='/save-filter'>
  <input type='text' name='target_model' value='{self.state.filter_model}'>
  <input type='number' name='target_id' value='{self.state.filter_id}'>
  <input type='number' name='target_ch' value='{self.state.filter_channel}'>
  <input type='checkbox' name='filter_enabled' value='1' {'checked' if self.state.filter_enabled else ''}>
  <button type='submit'>Ulozit a aplikovat filtr</button>
</form>
</div>
<script>var isTyping = false;</script>
</body></html>"""
            self._send_html(html)

        elif path == "/filter":
            html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>LilyGO - Nastavení filtru senzoru (SIMULATOR)</title></head><body>
<h1>Ruční nastavení filtru 433 MHz</h1>
<form method='POST' action='/save-filter'>
  <input type='text' name='target_model' value='{self.state.filter_model}'>
  <input type='number' name='target_id' value='{self.state.filter_id}'>
  <input type='number' name='target_ch' value='{self.state.filter_channel}'>
  <input type='checkbox' name='filter_enabled' value='1' {'checked' if self.state.filter_enabled else ''}>
  <button type='submit'>Uložit nastavení filtru</button>
</form>
</body></html>"""
            self._send_html(html)

        elif path == "/setup":
            html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>LilyGO - Nastavení WiFi a IP (SIMULATOR)</title></head><body>
<h1>LilyGO 433MHz - Nastavení WiFi</h1>
<form method='POST' action='/save'>
  <input type='text' name='ssid' value='{self.state.wifi_ssid}'>
  <input type='password' name='pass' value=''>
  <button type='submit'>Uložit</button>
</form>
</body></html>"""
            self._send_html(html)

        elif path == "/set-filter":
            if "model" in qs:
                self.state.filter_model = qs["model"][0].strip()
            if "id" in qs:
                self.state.filter_id = int(qs["id"][0])
            if "ch" in qs:
                self.state.filter_channel = int(qs["ch"][0])
            elif "channel" in qs:
                self.state.filter_channel = int(qs["channel"][0])
            if "enabled" in qs:
                en = qs["enabled"][0].lower()
                self.state.filter_enabled = en in ("1", "true", "on")
            else:
                self.state.filter_enabled = True

            redirect_url = qs.get("redirect", ["/debug"])[0]
            self._redirect(redirect_url)

        elif path == "/toggle-filter":
            self.state.filter_enabled = not self.state.filter_enabled
            redirect_url = qs.get("redirect", ["/debug"])[0]
            self._redirect(redirect_url)

        elif path in ("/repeat", "/tx"):
            self.state.tx_count += 1
            self._send_text(f"OK: Signal zopakovan (SIMULATOR). TX #{self.state.tx_count}\n")

        else:
            self._send_text("Not Found\n", status=404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8")
        data = urllib.parse.parse_qs(raw_body)

        if path in ("/save-filter", "/set-filter"):
            if "target_model" in data:
                self.state.filter_model = data["target_model"][0].strip()
            elif "model" in data:
                self.state.filter_model = data["model"][0].strip()

            if "target_id" in data:
                self.state.filter_id = int(data["target_id"][0])
            elif "id" in data:
                self.state.filter_id = int(data["id"][0])

            if "target_ch" in data:
                self.state.filter_channel = int(data["target_ch"][0])
            elif "ch" in data:
                self.state.filter_channel = int(data["ch"][0])

            self.state.filter_enabled = "filter_enabled" in data or data.get("enabled", ["0"])[0] == "1"
            redirect_url = data.get("redirect", ["/debug"])[0]
            self._redirect(redirect_url)

        elif path == "/save":
            if "ssid" in data:
                self.state.wifi_ssid = data["ssid"][0]
            self._send_html("<h2>Konfigurace ulozena (SIMULATOR)</h2>")

        elif path == "/reset":
            self.state.is_ap_mode = True
            self.state.wifi_ssid = ""
            self._send_html("<h2>Pamet vymazana (SIMULATOR)</h2>")

        else:
            self._send_text("Not Found\n", status=404)


def run_mock_server(port: int = DEFAULT_PORT):
    server_address = ("127.0.0.1", port)
    httpd = http.server.HTTPServer(server_address, GatewayMockHandler)
    print(f"LilyGO Mock Gateway Server running on http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping mock server.")
        httpd.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    run_mock_server(port)
