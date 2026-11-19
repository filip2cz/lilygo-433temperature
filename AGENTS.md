# AI Agent Guide — LilyGO 433MHz Weather Gateway

This repository contains the firmware and NixOS development environment for the **LilyGO LoRa32 T3_V1.6.1 433MHz** gateway. It captures 433.92 MHz radio packets from weather stations (such as EMOS E3070 / Kedsum-TH), displays readings on an onboard OLED display, exposes an HTTP web server, provides an AP Captive Portal for WiFi and IP setup, and can optionally re-transmit signals for a second station (EMOS E0688 / Hideki).

---

## Mandatory Rules for AI Agents

Whenever you modify or expand this codebase, **you must strictly follow these three rules**:

1. **Write code comments in English**: All source code comments, function docstrings, block headers, and code explanations within files (C++, Nix, scripts) must be written in **English**.
2. **Always update `README.md`**: If you add, change, or deprecate any user-facing feature, endpoint, build command, hardware configuration, or environment setup, immediately reflect the change in [README.md](file:///home/filip/git/lilygo-433temperature/README.md).
3. **Always update this agent documentation file (`AGENTS.md`)**: If you alter architecture patterns, add libraries, change hardware pin assignments, introduce new workflows, or modify data schemas, keep this file fully up-to-date for future AI agents.

---

## Hardware Architecture & Low-Level Constraints

### 1. Board & Microcontroller
- **Board Model**: LilyGO LoRa32 T3_V1.6.1 (433MHz revision)
- **MCU**: Espressif ESP32-PICO-D4 (System-in-Package with 4MB embedded SPI flash, 240MHz dual-core Xtensa LX6).
- **CRITICAL HARDWARE WARNING — GPIO 16**:
  - On the **ESP32-PICO-D4**, **GPIO 16** and **GPIO 17** are connected internally to the SPI flash (`CS`/`IO` pins).
  - **NEVER** use GPIO 16 (often labeled as OLED reset on standard ESP32-WROOM boards) or GPIO 17 as GPIO pins! Driving GPIO 16 will immediately crash the MCU with an SPI bus conflict or flash corruption error (`SPI_FAST_FLASH_BOOT` panic).
  - The OLED reset pin must always be set to `-1` (`#define OLED_RESET_PIN -1`), because OLED reset is tied to the board's main reset line.

### 2. Onboard SSD1306 OLED Display (0.96", 128×64)
- **Interface**: I²C (`Wire`)
- **Pins**: `SDA = 21`, `SCL = 22`
- **I²C Address**: `0x3C`
- **Display Layout**:
  - Line 0..10: Top status bar showing WiFi IP address (`IP: 192.168.x.x`) or Access Point status (`AP: 192.168.4.1`), separated by a horizontal line.
  - Line 18..46: Main readout showing temperature in large font (`XX.X C` or `--.- C`).
  - Line 48..64: Bottom status bar showing station info, elapsed seconds since last packet reception (`Kedsum CH1: 15s`), repeater stats (`RX:15s|TX#4`), or setup SSID (`SSID: LilyGO-Setup`).

### 3. Semtech SX1278 RF Transceiver (433.92 MHz)
- **SPI Pins**: `SCK = 5`, `MISO = 19`, `MOSI = 27`, `NSS / CS = 18`, `RST = 23`
- **Interrupt / DIO Pins**:
  - `DIO0 = 26` (Packet Done interrupt)
  - `DIO1 = 33`
  - `DIO2 = 32` (Direct Data demodulation RX / direct modulation TX)
- **Reception Stack**:
  - Handled by `rtl_433_ESP` library in direct OOK demodulation mode on 433.92 MHz (`OOK_FIXED_THRESHOLD = 0x50`).
  - The callback function receives JSON formatted string: `{"model":"Kedsum-TH","id":186,"channel":1,...}`.
- **Repeater / Transmission Stack (Hideki / Cresta protocol for EMOS E0688)**:
  - RadioLib is used alongside `rtl_433_ESP`.
  - When transmitting: SPI mutex lock (`rtl_433_ESP::spiTake(portMAX_DELAY)`) is acquired, receiver disabled, radio switched to direct OOK transmit via `radio.transmitDirect()`, and Manchester-encoded packets are pulsed onto `RF_MODULE_DIO2` (GPIO 32).
  - After transmission: Radio switched back to receive mode (`radio.receiveDirect()`), SPI lock released (`rtl_433_ESP::spiGive()`), and receiver re-enabled.

---

## WiFi Management & Captive Portal Architecture

Configuration is stored in non-volatile storage (NVS) using ESP32's native `Preferences` library (namespace: `"weather-wifi"`):

### State Machine & Flow:
1. **Boot / Check**:
   - `loadWifiConfig()` reads `ssid`, `pass`, `static_ip` (bool), `ip`, `gw`, `mask`, `dns`.
   - If `ssid` is empty (initial out-of-the-box boot or after `/reset`), `startAPMode()` is called.
2. **Access Point (AP) Mode**:
   - Starts softAP `LilyGO-Weather-Setup` without password.
   - Sets IP to `192.168.4.1`.
   - Runs `DNSServer` on port 53 mapping all domain requests (`*`) to `192.168.4.1`.
   - Root requests `/` in AP mode automatically serve the `/setup` configuration page.
   - Captive portal detection endpoints (`/generate_204`, `/hotspot-detect.html`, `/ncsi.txt`) return the setup page to auto-launch the captive popup on iOS, macOS, Android, and Windows.
3. **Station (STA) Mode**:
   - If SSID is present, attempts to connect.
   - If `static_ip == true`, applies IP/Gateway/Subnet/DNS via `WiFi.config()`; otherwise uses DHCP.
   - If connection fails within 20s, falls back to AP mode temporarily so user is never locked out.
4. **Web Setup Endpoints**:
   - `GET /setup`: HTML interface. Performs background WiFi scan and displays available SSIDs in a dropdown. Allows selecting DHCP or configuring Static IP.
   - `POST /save`: Parses POST arguments, saves them with `saveWifiConfig()`, confirms to user, and reboots MCU after 1.5s delay.
   - `POST /reset`: Calls `clearWifiConfig()`, clearing NVS, and restarts into AP mode.

---

## HTTP Web API Endpoints

The web server runs on port 80:

| Endpoint | Method | Description | Content-Type |
|---|---|---|---|
| `GET /` | GET | Plain temperature float string (e.g. `21.4\n`) or NaN (`503 NaN\n`). In AP mode, shows setup page. | `text/plain` |
| `GET /temp` | GET | Identical to `/` in STA mode. | `text/plain` |
| `GET /setup` | GET | Interactive WiFi & IP configuration and RF sensor filter interface. | `text/html` |
| `GET /filter` | GET | Dedicated manual RF sensor filter configuration page (model, ID, CH, enable/disable toggle) with list of discovered sensors. | `text/html` |
| `POST /save` | POST | Form action to save WiFi & IP settings to NVS and reboot. | `text/html` |
| `POST /save-filter` | POST | Form action to configure sensor model filter (persists in NVS namespace `weather-flt`, supports redirect parameter). | `text/html` (302) |
| `GET /set-filter` | GET/POST | Sets target model/ID/channel filter directly from query params (`?model=...&id=...&ch=...&enabled=...&redirect=...`), activates filter, and redirects. | `text/plain` (302) |
| `GET /toggle-filter` | GET | Instant toggle of sensor model filter with redirect back to referrer or `/debug`. | `text/plain` (302) |
| `POST /reset` | POST | Clears saved WiFi credentials and reboots into AP mode. | `text/html` |
| `GET /debug` | GET | Real-time dark-mode HTML dashboard showing last 35 received packets, embedded manual filter configuration form (with auto-refresh pause while typing), filter toggle, repeater metrics, and links. | `text/html` |
| `GET /raw` | GET | Plain-text raw packet log suitable for shell scripting / curl. | `text/plain` |
| `GET /json` | GET | JSON payload containing current temperature, humidity, sensor ID, WiFi status, filter state, and repeater counters. | `application/json` |
| `GET /repeat` or `/tx` | GET | Triggers on-demand repeater transmission of latest Kedsum reading. | `text/plain` |

---

## NixOS Development & Toolchain

The repository includes a declarative [shell.nix](file:///home/filip/git/lilygo-433temperature/shell.nix).

### Environment Commands:
- `nix-shell` — Drops into dev shell with PlatformIO and helper aliases.
- Available convenience commands inside or via `nix-shell --run <cmd>`:
  - `build` — Compiles the project (`pio run`).
  - `upload` — Flashes binary to connected board (`pio run -t upload`).
  - `monitor` — Opens serial monitor at 115200 baud (`pio device monitor`).
  - `flash` — Builds, uploads, and immediately opens the monitor (`pio run -t upload && exec pio device monitor`).
  - `runtests` — Executes the complete automated test suite (`python3 tests/run_tests.py`).

### Automated Test Suite (`tests/`):
- `tests/test_filter_logic.py`: Unit tests for matching algorithm (wildcards, case-insensitivity, enabled/disabled state).
- `tests/test_hideki_repeater.py`: Bitwise tests for Hideki / Cresta protocol encoding, packet byte layout, and checksum calculations.
- `tests/test_rtl433_parser.py`: JSON packet parsing for various sensor models and ring log buffer capping.
- `tests/test_device_api.py`: Hardware integration tests exercising live HTTP endpoints against `BOARD_URL` (default `http://192.168.1.50`).
- `tests/run_tests.py`: Python unittest discovery runner.

### PlatformIO Configuration (`platformio.ini`):
- **Board**: `ttgo-lora32-v21`
- **Platform**: `espressif32@6.1.0` (Arduino core 2.0.7)
- **Partition Scheme**: `board_build.partitions = huge_app.csv` (Provides ~3.1MB flash partition to comfortably house rtl_433_ESP, RadioLib, WebServer, and Adafruit GFX).
- **Serial Ports**: Autodetects `/dev/ttyACM0` or `/dev/ttyUSB0`.
- **Upload Speed**: `921600` baud.
- **Monitor Speed**: `115200` baud.

---

## Guidelines for Making Changes

1. **Keep Code English**:
   - Comments: English only.
   - Code variable & function names: English only.
   - User-facing UI strings on web interface and OLED can remain localized (Czech) as originally requested by the user, but code structure and explanations must be English.
2. **Check SPI Bus Integrity**:
   - Never initiate an RF transmission while the receiver is actively reading from the SPI bus without acquiring `rtl_433_ESP::spiTake()`.
3. **Preserve Huge App Partitioning**:
   - Due to the size of the RTL-433 decoding tables, do not remove `huge_app.csv` partition layout without checking flash boundaries.
4. **Synchronize Documentation**:
   - Modify `README.md` and `AGENTS.md` whenever adding endpoints, configuration parameters, or dependencies.
