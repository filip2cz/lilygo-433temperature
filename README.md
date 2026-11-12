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
- **OLED Display (SSD1306)**: Shows the assigned IP address, connection status, large temperature reading (`X.X °C`), reception age, and repeater transmit counter (`TX #N`).
- **Minimalist HTTP Web Server**:
  - `GET /` (and default route): Returns **purely the temperature number** as plain text (e.g. `4.7\n`), matching the exact design specification for simple integrations and shell scripts.
  - `GET /debug`: Live HTML diagnostic dashboard (auto-refreshing every 4s) displaying captured packets with filter badges (`[AKCEPTOVANO]` vs `[IGNOROVANO]`), repeater status, RSSI, and raw JSON payloads.
  - `GET /raw`: Clean plain text signal log suitable for `curl`.
  - `GET /json`: Structured JSON response with temperature, humidity, sensor ID, channel, and repeater metrics.
  - `GET /repeat` (or `/tx`): On-demand HTTP trigger to immediately broadcast the latest reading to the second station.
- **Static IP & DHCP Support**: Built-in toggle to specify a static IP address, gateway, subnet mask, and DNS, or use automatic DHCP from your router.
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

In [src/main.cpp](file:///home/filip/git/lilygo-433temperature/src/main.cpp) (or [lilygo-433temperature.ino](file:///home/filip/git/lilygo-433temperature/lilygo-433temperature.ino)):

### 1. WiFi & IP Settings
```cpp
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Set to true for static IP, or false for DHCP:
const bool USE_STATIC_IP  = true;

IPAddress STATIC_IP(192, 168, 1, 200);   // Target static IP
IPAddress GATEWAY(192, 168, 1, 1);       // Router gateway
IPAddress SUBNET(255, 255, 255, 0);     // Subnet mask
IPAddress PRIMARY_DNS(192, 168, 1, 1);   // Primary DNS
IPAddress SECONDARY_DNS(8, 8, 8, 8);    // Secondary DNS
```

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

### 2. Single-line Commands from Terminal
You can also run any command directly from your system terminal without entering the interactive shell:
```bash
nix-shell --run upload
nix-shell --run monitor
nix-shell --run flash
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
Open `http://192.168.1.200/debug` in any web browser to view the real-time dark-mode table of all incoming packets with visual acceptance tags.

---

## AI Tools & Development Transcript

This project was developed through an interactive vibecoding session using:
- **AI Coding Assistant**: [Google Antigravity](https://deepmind.google/technologies/gemini/)
- **Large Language Model**: Gemini 3.8 Flash (High) by Google DeepMind
- **Environment**: NixOS Linux

Read the full transcript of questions, troubleshooting steps, and architectural decisions in [CONVERSATION.md](file:///home/filip/git/lilygo-433temperature/CONVERSATION.md).

---

## License

This project is licensed under the [MIT License](file:///home/filip/git/lilygo-433temperature/LICENSE).
