# LilyGO LoRa32 433MHz — EMOS E3070 Weather Station Gateway

A standalone wireless bridge running on the **LilyGO LoRa32 T3_V1.6.1 433MHz** that captures 433.92 MHz radio signals from an **EMOS E3070** home weather station (outdoor sensor **E03070**), displays the real-time temperature on the onboard OLED screen, and serves the temperature over a local WiFi HTTP web server.

> [!NOTE]
> **Vibecoded with AI**: This entire project was **vibecoded** end-to-end in collaboration with **Google Antigravity** using the **Gemini 3.8 Flash (High)** model by Google DeepMind. The assistant researched the radio protocols, identified low-level hardware pin clashes (such as the ESP32-PICO-D4 internal flash CS on GPIO 16), decoded neighbor signals, tuned the filter for `Kedsum-TH`, and verified reproducible compilation under NixOS.
> 
> The complete pair-programming transcript is recorded in [CONVERSATION.md](file:///home/filip/git/lilygo-433temperature/CONVERSATION.md).

---

## Features

- **433.92 MHz RF Reception**: Uses the onboard Semtech SX1278 transceiver in direct OOK demodulation mode via the [rtl_433_ESP](https://github.com/NorthernMan54/rtl_433_ESP) library.
- **Signal Repeater (EMOS E0688 / Hideki)**: Automatically re-transmits the captured temperature (and humidity) for a second home weather station using the Hideki / Cresta protocol via direct OOK transmission on pin DIO2 (GPIO 32).
- **Protocol Filtering**: Automatically isolates your **EMOS E3070** sensor (which transmits under the `Kedsum-TH` protocol family) and discards irrelevant neighbor stations (e.g. `Acurite-606TX`).
- **OLED Display (SSD1306)**: Shows the assigned IP address (or AP mode status), connection status, large temperature reading (`X.X °C`), reception age, and repeater transmit counter (`TX #N`).
- **Minimalist HTTP Web Server**:
  - `GET /` (and default route): In regular WiFi STA mode returns **purely the temperature number** as plain text (e.g. `4.7\n`). In AP setup mode it automatically displays the WiFi configuration page.
  - `GET /setup`: Interactive web interface to configure WiFi credentials (SSID scan & select, password) and IP address mode (DHCP vs. static IP with IP, Gateway, Subnet mask, and DNS).
  - `GET /filter`: Dedicated standalone web interface to manually configure and tune the 433 MHz RF sensor filter (target model, sensor ID, channel, enable/disable toggle) with a click-to-pick list of recently detected sensors.
  - `GET /debug`: Live HTML diagnostic dashboard with embedded **Ruční nastavení filtru** (manual filter configuration form with datalist support for detected models, active editing detection to pause auto-refresh), table of captured packets with filter badges (`[AKCEPTOVANO]` vs `[IGNOROVANO]`), click-to-filter on any row, WiFi status link, repeater status, RSSI, and raw JSON payloads.
  - `GET /raw`: Clean plain text signal log suitable for `curl`.
  - `GET /json`: Structured JSON response with temperature, humidity, sensor ID, channel, WiFi details, active filter state, and repeater metrics.
  - `GET /set-filter`: Query-based filter configuration (`/set-filter?model=...&id=...&ch=...&enabled=...&redirect=...`).
  - `GET /toggle-filter`: Instant toggle of sensor model filter.
  - `GET /repeat` (or `/tx`): On-demand HTTP trigger to immediately broadcast the latest reading to the second station.
- **WiFi Captive Portal & Persistent NVS Storage**: If no WiFi credentials are stored in non-volatile storage (NVS via `Preferences`), the board automatically starts its own WiFi Access Point (`LilyGO-Weather-Setup` on `192.168.4.1`) with a captive portal redirecting any browser directly to `/setup`.
- **Static IP & DHCP Support**: Fully configurable through the web interface with persistence across reboots.
- **NixOS Ready**: Ships with a declarative [shell.nix](file:///home/filip/git/lilygo-433temperature/shell.nix) providing PlatformIO and necessary tools out of the box.

---

## Hardware Specifications

- **Board**: LilyGO LoRa32 T3_V1.6.1 (433 MHz revision)
- **MCU**: Espressif ESP32-PICO-D4 (240 MHz Dual Core, 4MB embedded flash)
- **RF Chip**: Semtech SX1278 (433.92 MHz, SPI interface)
  - `SCK=5`, `MISO=19`, `MOSI=27`, `NSS=18`, `RST=23`, `DIO0=26`, `DIO1=33`, `DIO2=32` (Direct Data RX)
- **Display**: 0.96" SSD1306 I²C OLED (128×64)
  - `SDA=21`, `SCL=22`, `RST=-1` (Hardware tied to board reset; *avoid GPIO 16 on PICO-D4 as it connects to internal flash CS*)
- **Target Weather Sensor**: EMOS E3070 / E03070 (Decoded as `Kedsum-TH`)

---

## Configuration

### 1. WiFi & IP Settings (Web Setup / AP Mode)
Upon initial power-on (or if saved WiFi cannot be reached):
1. The board automatically starts an open WiFi hotspot named **`LilyGO-Weather-Setup`**.
2. Connect your phone or computer to this WiFi network.
3. Open `http://192.168.4.1/` (or `http://192.168.4.1/setup`) in your web browser (Captive portal triggers automatically on Android/iOS/Windows).
4. Select your home WiFi from the scan list (or type the SSID), enter your password, choose DHCP or Static IP, and click **Uložit a restartovat zařízení**.
5. All settings are persistently saved to ESP32 NVS memory via `Preferences` and automatically re-used on all subsequent reboots.
6. To reconfigure later, simply visit `http://<BOARD_IP>/setup` or use the reset button to return to AP mode.

### 2. Sensor Filter
```cpp
// Target sensor model (EMOS E3070 identifies as Kedsum-TH):
const char* TARGET_MODEL  = "Kedsum-TH";
const int   TARGET_ID     = -1; // -1 for any ID, or specify exact ID (e.g. 186)
const int   TARGET_CHANNEL= -1; // -1 for any channel, or specify channel number
```

### 3. Repeater Settings (EMOS E0688 / Hideki)
```cpp
const bool          REPEATER_ENABLED    = true;   // Enable/disable repeating
const byte          REPEATER_SENSOR_ID  = 0x0C;   // Sensor ID byte for Hideki protocol (0x00 - 0x1F)
const byte          REPEATER_CHANNEL    = 1;      // Transmit channel (1, 2, or 3)
const int8_t        REPEATER_TX_POWER   = 10;     // TX Power in dBm (10 dBm = 10 mW)
const bool          REPEAT_ON_RECEIVE   = true;   // Auto-repeat immediately when new packet arrives
const unsigned long REPEAT_INTERVAL_MS  = 30000;  // Periodic repeat in ms (30s; 0 to disable periodic)
```

---

## Building and Flashing

A custom [shell.nix](file:///home/filip/git/lilygo-433temperature/shell.nix) is provided with PlatformIO and pre-configured helper commands:

### 1. Interactive Nix Shell (Recommended)
Simply enter the development shell:
```bash
nix-shell
```
Upon entering, you have access to short helper commands:
- **`build`** — Compiles the firmware (`pio run`)
- **`upload`** — Uploads firmware to the connected board (`pio run -t upload`)
- **`monitor`** — Opens serial monitor at 115200 baud (`pio device monitor`)
- **`flash`** — One-shot command: builds, uploads, and immediately opens the monitor!
- **`runtests`** — Runs the complete automated test suite (`python3 tests/run_tests.py`)!

### 2. Single-line Commands from Terminal
You can also run any command directly from your system terminal without entering the interactive shell:
```bash
nix-shell --run upload
nix-shell --run monitor
nix-shell --run flash
nix-shell --run runtests
```

### 3. Automated Test Suite (`tests/`)
The repository includes automated unit and integration tests under the [`tests/`](file:///home/filip/git/lilygo-433temperature/tests) directory:
- **`tests/test_filter_logic.py`**: Unit tests for sensor matching (model, ID, channel, wildcard handling).
- **`tests/test_hideki_repeater.py`**: Unit tests for Hideki / Cresta protocol encoding and checksums.
- **`tests/test_rtl433_parser.py`**: Unit tests for rtl_433 JSON message decoding and log ring buffer.
- **`tests/test_device_api.py`**: Live hardware integration tests verifying all HTTP endpoints (`/`, `/json`, `/raw`, `/debug`, `/filter`, `/setup`, `/save-filter`, `/set-filter`, `/toggle-filter`).
- **`tests/run_tests.py`**: Unified test discovery and execution runner.

Run all tests:
```bash
nix-shell --run runtests
# or directly:
python3 tests/run_tests.py
```

### 3. Non-NixOS Systems
If using standard PlatformIO:
```bash
pio run -t upload
pio device monitor
```

---

## Web API Examples

Once connected, the board's IP address appears on the OLED display and serial monitor.

### 1. Plain Temperature Only (`GET /`)
```bash
curl http://192.168.1.200/
# Output:
4.7
```

### 2. JSON API (`GET /json`)
```bash
curl http://192.168.1.200/json
# Output:
{"temperature":4.66667,"model":"Kedsum-TH","id":186,"channel":1,"battery_ok":0,"updated_s_ago":12}
```

### 3. Debug Raw Signal Log (`GET /raw`)
```bash
curl http://192.168.1.200/raw
# Output:
[12s zpet] [OK] {"model":"Kedsum-TH","id":186,"channel":1,"battery_ok":0.1,"temperature_C":4.66667,"humidity":83,...}
[45s zpet] [IGN] {"model":"Acurite-606TX","id":149,"battery_ok":1,"temperature_C":5.9,...}
```

### 4. Interactive Debug Dashboard (`GET /debug`)
Open `http://192.168.1.200/debug` in any web browser to view the real-time dark-mode table of all incoming packets with visual acceptance tags and one-click filter toggling.

### 5. WiFi & Filter Configuration (`GET /setup`)
Open `http://192.168.1.200/setup` to configure WiFi SSID/password, DHCP vs Static IP, and toggle the 433 MHz sensor filter (accept Kedsum-TH only vs any sensor). Settings are stored in non-volatile flash storage (NVS / Preferences).

---

## AI Tools & Development Transcript

This project was developed through an interactive vibecoding session using:
- **AI Coding Assistant**: [Google Antigravity](https://deepmind.google/technologies/gemini/)
- **Large Language Model**: Gemini 3.8 Flash (High) by Google DeepMind
- **Environment**: NixOS Linux

Read the full transcript of questions, troubleshooting steps, and architectural decisions in [CONVERSATION.md](file:///home/filip/git/lilygo-433temperature/CONVERSATION.md).

For AI agents contributing to this codebase, see the mandatory development guidelines and hardware documentation in [AGENTS.md](file:///home/filip/git/lilygo-433temperature/AGENTS.md).

---

## License

This project is licensed under the [MIT License](file:///home/filip/git/lilygo-433temperature/LICENSE).
