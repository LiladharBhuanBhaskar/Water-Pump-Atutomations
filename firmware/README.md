# 🔌 HydraControl — ESP32 Breadboard Circuit & Firmware Guide

This directory contains the production ESP32 firmware configured for the exact breadboard circuit: **HC-SR04 Ultrasonic Sensor + Analog Turbidity Sensor + 3-Pin Buzzer Module**.

---

## 📐 Circuit Wiring & GPIO Map

| Component | Component Pin | Connection on Breadboard | ESP32 GPIO | Voltage Protection |
| :--- | :--- | :--- | :--- | :--- |
| **HC-SR04 Ultrasonic** | **VCC** | 5V Red Rail (from 5V DC Supply) | — | Powered via 5V |
| | **GND** | GND Blue Rail | — | Common GND |
| | **TRIG** | Direct jumper wire (Blue wire) | **GPIO 18** | Standard 3.3V output trigger |
| | **ECHO** | Through **10kΩ + 15kΩ** divider (Yellow wire) | **GPIO 19** | Steps down 5V echo pulse to safe **~3.0V** |
| **Turbidity Sensor** | **VCC / +** | 5V Red Rail (from 5V DC Supply) | — | Powered via 5V |
| | **GND / -** | GND Blue Rail | — | Common GND |
| | **AO (Analog)** | Through **10kΩ + 10kΩ** divider (Purple wire) | **GPIO 34** | Steps down 4.5V output to safe **~2.25V** |
| | **DO** | Not connected | — | Analog AO used for clarity |
| **Buzzer Module (3-Pin)** | **VCC / +** | ESP32 3.3V Pin (Red wire) | **3V3** | 3.3V logic level |
| | **GND / -** | GND Blue Rail (Black wire) | — | Common GND |
| | **S / IN** | Direct jumper wire (Green wire) | **GPIO 25** | Active digital buzzer drive |
| **Status / Actuators** | **Blue LED** | Built-in DevKit LED | **GPIO 2** | Indicates motor running & Wi-Fi state |
| | **Pump Relay** | Contactor Relay Module (optional) | **GPIO 26** | Active HIGH coil drive |

### ⚡ Why Voltage Dividers are Used:
1. **HC-SR04 ECHO Pin (5V $\to$ 3V)**:
   - The HC-SR04 outputs a $5\text{V}$ echo signal. Connecting $5\text{V}$ directly to an ESP32 pin can damage the chip over time.
   - The $10\text{k}\Omega$ (top) and $15\text{k}\Omega$ (bottom to GND) divider scales the voltage:
     $$V_{\text{ESP32}} = 5\text{V} \times \frac{15\text{k}\Omega}{10\text{k}\Omega + 15\text{k}\Omega} = 5\text{V} \times 0.60 = 3.0\text{V}$$
2. **Turbidity Sensor AO Pin (4.5V $\to$ 2.25V)**:
   - The gravity turbidity interface board outputs up to $4.5\text{V}$.
   - The $10\text{k}\Omega$ (top) and $10\text{k}\Omega$ (bottom to GND) divider scales the voltage by $0.5$:
     $$V_{\text{ESP32}} = 4.5\text{V} \times \frac{10\text{k}\Omega}{10\text{k}\Omega + 10\text{k}\Omega} = 2.25\text{V}$$
   - The firmware automatically multiplies the measured ADC voltage by $2.0\times$ to recover the true sensor reading!

---

## 🚀 How to Upload the Code in Arduino IDE

We provide a self-contained, pre-configured sketch inside:
[`firmware/HydraControl_ESP32/HydraControl_ESP32.ino`](file:///c:/Users/bhask/OneDrive/Desktop/water%20pump%20automations/firmware/HydraControl_ESP32/HydraControl_ESP32.ino)

### Step 1: Open Arduino IDE
1. Open the **Arduino IDE** (v1.8.x or v2.x).
2. Go to **File $\to$ Open...** and select:
   ```
   firmware/HydraControl_ESP32/HydraControl_ESP32.ino
   ```

### Step 2: Install Required Libraries
Open **Sketch $\to$ Include Library $\to$ Manage Libraries...** and install:
1. **PubSubClient** by Nick O'Leary
2. **ArduinoJson** by Benoît Blanchon (version 6.x or 7.x)

### Step 3: Configure Your Wi-Fi
In `HydraControl_ESP32.ino` (lines 43–44), set your Wi-Fi SSID and password:
```cpp
const char* WIFI_SSID     = "Your_WiFi_Name";
const char* WIFI_PASSWORD = "Your_WiFi_Password";
```

### Step 4: Plug In and Upload
1. Connect your ESP32 via USB cable to your computer.
2. Select your board under **Tools $\to$ Board $\to$ ESP32 Arduino $\to$ ESP32 Dev Module**.
3. Select your serial port under **Tools $\to$ Port** (e.g. `COM3`, `COM4`, or `/dev/ttyUSB0`).
4. Click the **Upload** button (Arrow icon in toolbar).
5. Open **Tools $\to$ Serial Monitor** and set baud rate to **115200**.

---

## 🔔 Audible Beep Codes (Buzzer on GPIO25)

| Event | Buzzer Tone Pattern |
| :--- | :--- |
| **Power On / Boot** | 1 medium beep (150ms) |
| **Wi-Fi Connected** | 2 quick beeps (60ms each) |
| **MQTT Cloud Connected** | 3 cheerful beeps (50ms each) |
| **Motor START command** | 2 affirmative beeps (100ms each) |
| **Motor STOP command** | 1 solid stop tone (250ms) |
| **Fault Trip / Alarm** | Continuous pulsing alarm (200ms ON / 800ms OFF) |
| **Fault Cleared / Reset** | 1 long confirmation tone (400ms) |

---

## 📊 Live Telemetry Streamed to Web & Mobile App

The ESP32 publishes live JSON telemetry every 2 seconds to `hydracontrol/devices/HYDRA-PROD-ESP32-001/telemetry`:
```json
{
  "device_uid": "HYDRA-PROD-ESP32-001",
  "timestamp": 1728821000,
  "motor_state": "ON",
  "sensors": {
    "water_level_pct": 82.4,
    "turbidity_ntu": 3.8,
    "distance_cm": 18.2,
    "current_amps": 5.8,
    "voltage": 230.0,
    "flow_rate": 42.5
  }
}
```
You can view these values in real-time in the HydraControl web dashboard and Android APK mobile app.
