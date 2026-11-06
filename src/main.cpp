#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ArduinoJson.h>
#include <ArduinoLog.h>
#include <rtl_433_ESP.h>

// ==========================================
// 1. Nastavení WiFi a IP adresy
// ==========================================
const char* WIFI_SSID     = "SSID";
const char* WIFI_PASSWORD = "PASSWORD";

// Nastavte USE_STATIC_IP na true pro statickou IP, nebo false pro DHCP:
const bool USE_STATIC_IP  = false;

// Parametry statické IP adresy (upravte podle své domácí sítě):
IPAddress STATIC_IP(192, 168, 1, 206);   // Požadovaná statická IP adresa desky
IPAddress GATEWAY(192, 168, 1, 1);       // Výchozí brána (IP adresa routeru)
IPAddress SUBNET(255, 255, 255, 0);     // Maska podsítě
IPAddress PRIMARY_DNS(192, 168, 1, 1);   // Primární DNS server (router nebo např. 8.8.8.8)
IPAddress SECONDARY_DNS(8, 8, 8, 8);    // Sekundární DNS server (volitelné)

// ==========================================
// 2. Filtrování cílového čidla
// Ignorujeme všechny cizí stanice a přijímáme pouze Kedsum-TH
// ==========================================
const char* TARGET_MODEL  = "Kedsum-TH";
const int   TARGET_ID     = -1; // -1 = jakékoliv ID (nebo 186 pro fixaci na jedno čidlo)
const int   TARGET_CHANNEL= -1; // -1 = jakýkoliv kanál (nebo 1 pro kanál 1)

// ==========================================
// 3. Nastavení OLED displeje (LilyGO T3_V1.6.1)
// POZOR: Na čipu ESP32-PICO-D4 je GPIO 16 vyhrazen pro interní SPI Flash!
// Reset OLEDu na této revizi desky není vyveden na GPIO (použijeme -1).
// ==========================================
#define SCREEN_WIDTH    128
#define SCREEN_HEIGHT   64
#define OLED_SDA        21
#define OLED_SCL        22
#define OLED_RESET_PIN  -1

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET_PIN);

// ==========================================
// 4. Webový server na portu 80
// ==========================================
WebServer server(80);

// ==========================================
// 5. 433 MHz přijímač (rtl_433_ESP / SX1278)
// ==========================================
#ifndef RF_MODULE_FREQUENCY
#  define RF_MODULE_FREQUENCY 433.92
#endif

#define JSON_MSG_BUFFER 512
char messageBuffer[JSON_MSG_BUFFER];
rtl_433_ESP rf;

// Globální proměnné pro stav a teplotu
float currentTemperature = NAN;
String lastModel = "";
int lastId = -1;
int lastChannel = -1;
int lastBatteryOk = -1;
unsigned long lastPacketTime = 0;
unsigned long lastDisplayRefresh = 0;

// Stavová zpráva pro WiFi na displeji
String wifiStatusMsg = "WiFi: Cekam...";

// ==========================================
// 6. Buffer pro zaznamenávání zachycených signálů (Debug)
// ==========================================
struct LogEntry {
  unsigned long timestamp;
  String rawJson;
  String model;
  int id;
  int channel;
  float temperature;
  int battery;
  int humidity;
  bool accepted;
};

#define MAX_LOG_ENTRIES 35
LogEntry debugLog[MAX_LOG_ENTRIES];
int debugLogCount = 0;

void addLogEntry(const String& raw, const String& model, int id, int channel, float temp, int bat, int hum, bool accepted) {
  if (debugLogCount < MAX_LOG_ENTRIES) {
    debugLogCount++;
  }
  for (int i = debugLogCount - 1; i > 0; i--) {
    debugLog[i] = debugLog[i - 1];
  }
  debugLog[0].timestamp = millis();
  debugLog[0].rawJson = raw;
  debugLog[0].model = model;
  debugLog[0].id = id;
  debugLog[0].channel = channel;
  debugLog[0].temperature = temp;
  debugLog[0].battery = bat;
  debugLog[0].humidity = hum;
  debugLog[0].accepted = accepted;
}

// ==========================================
// Vykreslení informací na OLED displej
// ==========================================
void updateDisplay() {
  display.clearDisplay();

  // Horní řádek: stav WiFi a IP adresa
  display.setTextSize(1);
  display.setCursor(0, 0);
  if (WiFi.status() == WL_CONNECTED) {
    display.print("IP: ");
    display.print(WiFi.localIP());
  } else {
    display.print(wifiStatusMsg);
  }

  // Oddělovací linka pod horním řádkem
  display.drawLine(0, 10, SCREEN_WIDTH - 1, 10, SSD1306_WHITE);

  // Střední část: Velká teplota
  display.setCursor(6, 18);
  if (isnan(currentTemperature)) {
    display.setTextSize(3);
    display.print("--.-");
    display.setTextSize(2);
    display.print(" C");
  } else {
    display.setTextSize(3);
    display.printf("%.1f", currentTemperature);
    display.setTextSize(2);
    display.print(" C");
  }

  // Oddělovací linka nad spodním řádkem
  display.drawLine(0, 48, SCREEN_WIDTH - 1, 48, SSD1306_WHITE);

  // Spodní řádek: model čidla a čas od posledního příjmu
  display.setTextSize(1);
  display.setCursor(0, 52);
  if (lastPacketTime > 0) {
    unsigned long secAgo = (millis() - lastPacketTime) / 1000;
    if (lastChannel >= 0) {
      display.printf("Kedsum CH%d: %lus", lastChannel, secAgo);
    } else {
      display.printf("Kedsum: %lus", secAgo);
    }
  } else {
    display.print("Cekam na Kedsum-TH");
  }

  display.display();
}

// ==========================================
// WiFi Event Handler pro diagnostiku
// ==========================================
void WiFiEvent(WiFiEvent_t event, WiFiEventInfo_t info) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_STA_START:
      Serial.println(F("[WiFi] Rozhrani spusteno..."));
      wifiStatusMsg = "WiFi: Pripojuji...";
      break;
    case ARDUINO_EVENT_WIFI_STA_CONNECTED:
      Serial.println(F("[WiFi] Pripojeno k AP, prirazuji IP..."));
      wifiStatusMsg = "WiFi: Overuji IP...";
      break;
    case ARDUINO_EVENT_WIFI_STA_GOT_IP:
      Serial.print(F("[WiFi] USPESNE PRIPOJENO! IP: "));
      Serial.println(IPAddress(info.got_ip.ip_info.ip.addr));
      wifiStatusMsg = "IP: " + IPAddress(info.got_ip.ip_info.ip.addr).toString();
      break;
    case ARDUINO_EVENT_WIFI_STA_DISCONNECTED: {
      uint8_t reason = info.wifi_sta_disconnected.reason;
      Serial.printf("[WiFi] Odpojeno. Reason: %d\n", reason);
      wifiStatusMsg = "WiFi: Odpojeno (" + String(reason) + ")";
      break;
    }
    default:
      break;
  }
  updateDisplay();
}

// ==========================================
// Web server handlery
// ==========================================
// Hlavní stránka: ČISTĚ JEN TEPLOTA (pouze číslo z čidla Kedsum-TH)
void handleRoot() {
  if (isnan(currentTemperature)) {
    server.send(503, "text/plain", "NaN\n");
  } else {
    server.send(200, "text/plain", String(currentTemperature, 1) + "\n");
  }
}

// Debug stránka s přehlednou tabulkou, stavem filtru a kopírovatelným výpisem signálů
void handleDebug() {
  String html = "";
  html.reserve(4096);
  html += "<!DOCTYPE html><html><head><meta charset='utf-8'>";
  html += "<meta http-equiv='refresh' content='4'>";
  html += "<title>LilyGO 433MHz - Zachycene signaly</title>";
  html += "<style>";
  html += "body { font-family: monospace, sans-serif; background: #161b22; color: #c9d1d9; padding: 20px; margin: 0; }";
  html += "h1 { color: #58a6ff; font-size: 20px; margin-bottom: 5px; }";
  html += ".filter-info { background: #1f242c; border-left: 4px solid #238636; padding: 10px 15px; margin: 15px 0; border-radius: 4px; font-size: 13px; line-height: 1.5; }";
  html += ".nav { margin-bottom: 15px; font-size: 13px; }";
  html += ".nav a { color: #58a6ff; text-decoration: none; margin-right: 15px; }";
  html += "table { border-collapse: collapse; width: 100%; margin-top: 10px; background: #0d1117; }";
  html += "th, td { border: 1px solid #30363d; padding: 8px 10px; text-align: left; font-size: 13px; }";
  html += "th { background: #21262d; color: #7ee787; }";
  html += "tr:nth-child(even) { background: #161b22; }";
  html += ".temp { font-weight: bold; color: #ffa657; font-size: 15px; }";
  html += ".json { word-break: break-all; color: #8b949e; font-size: 11px; }";
  html += "pre { background: #0d1117; color: #58a6ff; padding: 12px; border: 1px solid #30363d; overflow-x: auto; font-size: 12px; white-space: pre-wrap; }";
  html += ".badge-ok { background: #238636; color: white; padding: 2px 7px; border-radius: 10px; font-size: 11px; font-weight: bold; }";
  html += ".badge-ign { background: #484f58; color: #8b949e; padding: 2px 7px; border-radius: 10px; font-size: 11px; }";
  html += "</style></head><body>";

  html += "<h1>433 MHz Monitor - Zachycene signaly</h1>";
  html += "<div class='filter-info'>";
  html += "<b>Aktivni filtr:</b> Zpracovava se POUZE model: <code>";
  html += TARGET_MODEL;
  html += "</code> | Ostatni modely (Acurite atd.) jsou ignorovany.<br>";
  html += "<b>IP konfigurace:</b> ";
  if (USE_STATIC_IP) {
    html += "Staticka IP (";
    html += WiFi.localIP().toString();
    html += ")";
  } else {
    html += "DHCP (";
    html += WiFi.localIP().toString();
    html += ")";
  }
  html += "</div>";

  html += "<div class='nav'>";
  html += "Auto-refresh: 4s | ";
  html += "<a href='/raw'>Cisty text pro kopirovani (/raw)</a> | ";
  html += "<a href='/json'>JSON stav (/json)</a> | ";
  html += "<a href='/'>Hlavni stranka (jen cislo)</a>";
  html += "</div>";

  if (debugLogCount == 0) {
    html += "<p style='color: #8b949e;'><em>Zatim nebyl zachycen zadny 433 MHz signal. Cekam na vysilani...</em></p>";
  } else {
    html += "<table><tr><th>Cas</th><th>Stav filtru</th><th>Model zarizeni</th><th>ID cidla</th><th>Kanal</th><th>Teplota</th><th>Vlhkost</th><th>Kompletni surovy JSON</th></tr>";
    for (int i = 0; i < debugLogCount; i++) {
      unsigned long secAgo = (millis() - debugLog[i].timestamp) / 1000;
      html += "<tr>";
      html += "<td>";
      html += secAgo;
      html += "s zpet</td>";
      html += "<td>";
      if (debugLog[i].accepted) {
        html += "<span class='badge-ok'>AKCEPTOVANO</span>";
      } else {
        html += "<span class='badge-ign'>IGNOROVANO</span>";
      }
      html += "</td>";
      html += "<td><b>";
      html += debugLog[i].model;
      html += "</b></td>";
      html += "<td>";
      html += (debugLog[i].id >= 0 ? String(debugLog[i].id) : "-");
      html += "</td>";
      html += "<td>";
      html += (debugLog[i].channel >= 0 ? "CH " + String(debugLog[i].channel) : "-");
      html += "</td>";
      html += "<td class='temp'>";
      if (!isnan(debugLog[i].temperature)) {
        html += String(debugLog[i].temperature, 1);
        html += " &deg;C";
      } else {
        html += "-";
      }
      html += "</td>";
      html += "<td>";
      html += (debugLog[i].humidity >= 0 ? String(debugLog[i].humidity) + " %" : "-");
      html += "</td>";
      html += "<td>";
      html += (debugLog[i].battery >= 0 ? (debugLog[i].battery ? "OK" : "LOW") : "-");
      html += "</td>";
      html += "<td class='json'>";
      html += debugLog[i].rawJson;
      html += "</td>";
      html += "</tr>";
    }
    html += "</table>";

    html += "<h2 style='font-size:15px; margin-top:20px; color:#58a6ff;'>Surovy vypis pro zkopirovani do chatu:</h2>";
    html += "<pre>";
    for (int i = 0; i < debugLogCount; i++) {
      unsigned long secAgo = (millis() - debugLog[i].timestamp) / 1000;
      html += "[";
      html += secAgo;
      html += "s zpet] ";
      if (debugLog[i].accepted) {
        html += "[OK] ";
      } else {
        html += "[IGN] ";
      }
      html += debugLog[i].rawJson;
      html += "\n";
    }
    html += "</pre>";
  }

  html += "</body></html>";
  server.send(200, "text/html; charset=utf-8", html);
}

// Čistý textový výpis signálů pro curl nebo jednoduché zkopírování
void handleRaw() {
  String text = "";
  for (int i = 0; i < debugLogCount; i++) {
    unsigned long secAgo = (millis() - debugLog[i].timestamp) / 1000;
    text += "[" + String(secAgo) + "s zpet] " + (debugLog[i].accepted ? "[OK] " : "[IGN] ") + debugLog[i].rawJson + "\n";
  }
  if (text.length() == 0) {
    text = "Zatim zadne zachycene signaly.\n";
  }
  server.send(200, "text/plain; charset=utf-8", text);
}

// JSON endpoint s aktuálním stavem
void handleJson() {
  JsonDocument doc;
  if (!isnan(currentTemperature)) {
    doc["temperature"] = currentTemperature;
    doc["model"] = lastModel;
    if (lastId >= 0) doc["id"] = lastId;
    if (lastChannel >= 0) doc["channel"] = lastChannel;
    if (lastBatteryOk >= 0) doc["battery_ok"] = lastBatteryOk;
    doc["updated_s_ago"] = (millis() - lastPacketTime) / 1000;
  } else {
    doc["temperature"] = nullptr;
  }
  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response + "\n");
}

// ==========================================
// Callback při zachycení 433 MHz zprávy
// ==========================================
void rtl_433_Callback(char* message) {
  Serial.print(F("[RF zachyceno]: "));
  Serial.println(message);

  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, message);
  if (error) {
    Serial.printf("[JSON chyba]: %s\n", error.c_str());
    return;
  }

  String model = doc["model"].is<const char*>() ? doc["model"].as<String>() : "Neznamy";
  int id = doc["id"].is<int>() ? doc["id"].as<int>() : -1;
  int channel = doc["channel"].is<int>() ? doc["channel"].as<int>() : -1;
  int battery = doc["battery_ok"].is<int>() ? doc["battery_ok"].as<int>() : -1;
  int humidity = doc["humidity"].is<int>() ? doc["humidity"].as<int>() : -1;
  float temp = NAN;

  if (doc["temperature_C"].is<float>()) {
    temp = doc["temperature_C"].as<float>();
  } else if (doc["temperature_F"].is<float>()) {
    float tempF = doc["temperature_F"].as<float>();
    temp = (tempF - 32.0f) * 5.0f / 9.0f;
  }

  // Kontrola filtru: zajímá nás pouze Kedsum-TH
  bool isTarget = model.equalsIgnoreCase(TARGET_MODEL);
  if (isTarget && TARGET_ID >= 0 && id != TARGET_ID) {
    isTarget = false;
  }
  if (isTarget && TARGET_CHANNEL >= 0 && channel != TARGET_CHANNEL) {
    isTarget = false;
  }

  // Zaznamenat do debug logu (včetně stavu akceptace)
  addLogEntry(String(message), model, id, channel, temp, battery, humidity, isTarget);

  // Pokud paket NENÍ z Kedsum-TH, ignorujeme jej a nepřepisujeme teplotu!
  if (!isTarget) {
    Serial.printf("[RF IGNOROVANO]: Model '%s' neodpovida '%s'\n", model.c_str(), TARGET_MODEL);
    return;
  }

  // Pokud je to Kedsum-TH a obsahuje teplotu, aktualizujeme stav
  if (!isnan(temp)) {
    currentTemperature = temp;
    lastPacketTime = millis();
    lastModel = model;
    lastId = id;
    lastChannel = channel;
    lastBatteryOk = battery;

    Serial.printf("=> [KEDSUM-TH AKTUALIZOVANO] Teplota: %.1f C (ID: %d, CH: %d, Vlhkost: %d%%)\n",
                  currentTemperature, lastId, lastChannel, humidity);

    updateDisplay();
  }
}

// ==========================================
// Setup
// ==========================================
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println(F("\n=============================================="));
  Serial.println(F(" LilyGO LoRa32 433MHz - EMOS E3070 Receiver "));
  Serial.println(F("=============================================="));

  // 1. Inicializace OLED displeje (SSD1306 na pinech SDA=21, SCL=22)
  Wire.begin(OLED_SDA, OLED_SCL);
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println(F("[CHYBA] Inicializace SSD1306 selhala!"));
  } else {
    Serial.println(F("[OK] OLED displej pripraven."));
    display.setTextColor(SSD1306_WHITE);
    updateDisplay();
  }

  // 2. Kontrola a připojení k WiFi
  WiFi.onEvent(WiFiEvent);
  Serial.printf("[WiFi] Zahajuji pripojovani k: '%s'...\n", WIFI_SSID);
  wifiStatusMsg = "WiFi: Pripojuji...";
  updateDisplay();

  WiFi.disconnect(true);
  delay(100);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);

  // Konfigurace statické IP adresy, pokud je zapnuta
  if (USE_STATIC_IP) {
    if (!WiFi.config(STATIC_IP, GATEWAY, SUBNET, PRIMARY_DNS, SECONDARY_DNS)) {
      Serial.println(F("[WiFi CHYBA] Konfigurace staticke IP selhala!"));
    } else {
      Serial.print(F("[WiFi] Nastavena staticka IP: "));
      Serial.println(STATIC_IP);
    }
  }

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  // 3. Nastavení webového serveru
  server.on("/", HTTP_GET, handleRoot);
  server.on("/temp", HTTP_GET, handleRoot);
  server.on("/debug", HTTP_GET, handleDebug);
  server.on("/signals", HTTP_GET, handleDebug);
  server.on("/raw", HTTP_GET, handleRaw);
  server.on("/json", handleJson);
  server.onNotFound(handleRoot); // Výchozí fallback vrací číslo
  server.begin();
  Serial.println(F("[OK] Webovy server spusten na portu 80."));
  Serial.printf("[OK] Filtr nastaven POUZE na model '%s'\n", TARGET_MODEL);

  // 4. Inicializace rtl_433_ESP přijímače na SX1278 (433.92 MHz)
  Log.begin(LOG_LEVEL_NOTICE, &Serial);
  Serial.println(F("[RF] Inicializuji SX1278 433.92 MHz OOK prijimac..."));

  rf.initReceiver(RF_MODULE_RECEIVER_GPIO, RF_MODULE_FREQUENCY);
  rf.setCallback(rtl_433_Callback, messageBuffer, JSON_MSG_BUFFER);
  rf.enableReceiver();

  Serial.println(F("[OK] Prijimac aktivni, cekam na vysilani Kedsum-TH..."));
  updateDisplay();
}

// ==========================================
// Loop
// ==========================================
void loop() {
  // Zpracování RF paketů (rtl_433)
  rf.loop();

  // Zpracování HTTP požadavků
  server.handleClient();

  // Automatický reconnect WiFi při výpadku
  static unsigned long lastWifiReconnectAttempt = 0;
  if (WiFi.status() != WL_CONNECTED) {
    if (millis() - lastWifiReconnectAttempt > 15000) {
      lastWifiReconnectAttempt = millis();
      Serial.println(F("[WiFi] Obnovuji pokus o pripojeni..."));
      WiFi.reconnect();
    }
  }

  // Obnova OLED displeje každých 5 sekund (čas "X s zpět")
  if (millis() - lastDisplayRefresh > 5000) {
    lastDisplayRefresh = millis();
    updateDisplay();
  }
}
