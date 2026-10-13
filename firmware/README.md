# 🔌 HydraControl — ESP32 Firmware Guide

This folder contains the production firmware for physical ESP32 controllers connecting to the HydraControl platform.

---

## ⚡ Option 1: Direct Upload via Arduino IDE (Recommended & Easiest)

We provide a pre-packaged, single-file sketch inside [`firmware/HydraControl_ESP32/HydraControl_ESP32.ino`](file:///c:/Users/bhask/OneDrive/Desktop/water%20pump%20automations/firmware/HydraControl_ESP32/HydraControl_ESP32.ino).

### Step 1: Open Arduino IDE
1. Open the Arduino IDE.
2. Go to **File -> Open** and select:
   ```
   firmware/HydraControl_ESP32/HydraControl_ESP32.ino
   ```

### Step 2: Install Required Libraries
Open **Sketch -> Include Library -> Manage Libraries...** and install:
1. **PubSubClient** by Nick O'Leary
2. **ArduinoJson** by Benoît Blanchon

### Step 3: Enter Your Wi-Fi Credentials
At lines 30–31 of `HydraControl_ESP32.ino`, set your Wi-Fi name and password:
```cpp
const char* WIFI_SSID     = "Your_WiFi_Name";
const char* WIFI_PASSWORD = "Your_WiFi_Password";
```

### Step 4: Upload to ESP32
1. Plug your ESP32 board into your computer with a USB cable.
2. Select your board under **Tools -> Board -> ESP32 Arduino -> ESP32 Dev Module**.
3. Select your serial port under **Tools -> Port** (e.g. `COM3` or `COM4`).
4. Click the **Upload** button (arrow icon).
5. Open **Tools -> Serial Monitor** and set the baud rate to **115200**.

### 💡 Desk Testing (Bench Mode)
The firmware comes with `BENCH_TEST_MODE = true` enabled by default:
- You do **not** need physical float switches or sensors wired up to test immediately on your desk!
- When you click **START** in the Web or Mobile app, the **blue onboard LED (GPIO 2)** and relay pin (GPIO 25) will turn **ON**.
- When you click **STOP**, it turns **OFF**.
- When you are ready to wire real analog sensors and float switches, set `#define BENCH_TEST_MODE false`.

---

## 🛠️ Option 2: Upload via PlatformIO (VS Code)

If you use VS Code with the PlatformIO extension:
1. Open the `firmware/` directory in VS Code.
2. In [`firmware/include/config.h`](file:///c:/Users/bhask/OneDrive/Desktop/water%20pump%20automations/firmware/include/config.h), set your Wi-Fi credentials.
3. Click the PlatformIO **Upload** button (arrow in the bottom status bar) or run:
   ```bash
   pio run --target upload
   ```
4. Open the serial monitor:
   ```bash
   pio device monitor
   ```

---

## 📌 Hardware Pinout Mapping

| Component | ESP32 GPIO | Description |
| :--- | :--- | :--- |
| **Contactor Relay** | `GPIO 25` | Output (Active HIGH) to 5V relay module driving pump contactor |
| **Onboard Blue LED** | `GPIO 2` | Visual indicator for motor state and Wi-Fi connection |
| **Emergency Stop Button**| `GPIO 4` | Active LOW (with internal pullup), trips instant hardware latch |
| **Upper Tank Float Switch** | `GPIO 18` | Active LOW, triggers auto-cutoff when tank is 100% full |
| **Lower Sump Float Switch** | `GPIO 19` | Active LOW, trips dry run protection if water source is empty |
| **Current Sensor (ACS712)** | `GPIO 36 (VP)` | Analog input measuring motor current draw |
| **Turbidity Sensor** | `GPIO 39 (VN)` | Analog input measuring water clarity/sediment |
| **Water Level Sensor** | `GPIO 33` | Analog input (0–3.3V) for continuous water level % |

---

## 🌐 Remote Cloud Architecture

Both the backend and ESP32 connect to the public cloud MQTT broker:
- **Broker**: `broker.emqx.io`
- **Port**: `1883`
- **Device Topic Root**: `hydracontrol/devices/HYDRA-PROD-ESP32-001/`

No port-forwarding or local router configuration is needed. The ESP32 can be connected to any Wi-Fi network, mobile 4G hotspot, or cellular module anywhere in the world and communicate directly with your HydraControl platform.
