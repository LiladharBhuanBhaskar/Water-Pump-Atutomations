# HydraControl — Hardware Schematic, Pinout & Bill of Materials (BOM)
**Phase 26 — Production Hardware Specification**

> [!WARNING]
> **HIGH VOLTAGE / ELECTRICAL SAFETY WARNING**
> Single-phase (230V AC) and 3-phase (415V AC) pump motor installations carry severe electrical shock and fire hazards.
> **NEVER** connect an ESP32 GPIO pin directly to an AC pump motor. All motor control **MUST** be routed through an opto-isolated relay module driving an appropriately rated industrial magnetic contactor with overload protection. Mains electrical wiring must be performed exclusively by a licensed and certified electrician.

---

## 1. System Block Diagram

```
+-----------------------------------------------------------------------------------+
|                               HYDRACONTROL SYSTEM                                 |
|                                                                                   |
|  [ Cloud / Backend API / MQTT Broker ]                                            |
|                 ^                                                                 |
|                 | TLS / MQTT (Wi-Fi 802.11 b/g/n)                                 |
|                 v                                                                 |
|  +-----------------------------------------------------------------------------+  |
|  | ESP32-WROOM-32 Microcontroller (Authoritative Safety Engine)                |  |
|  |                                                                             |  |
|  |  [GPIO 34] <--- Emergency STOP Pushbutton (NC Contact)                      |  |
|  |  [GPIO 35] <--- Overhead Tank High Level Float Switch                       |  |
|  |  [GPIO 32] <--- Sump / Source Dry-Run Float Switch                         |  |
|  |  [GPIO 33] <--- Hydrostatic / Ultrasonic Level Sensor (0-3.3V ADC)          |  |
|  |  [GPIO 39] <--- Turbidity Sensor Module (0-3.3V ADC)                        |  |
|  |  [GPIO 36] <--- Hall-Effect Current Sensor (ACS712 / CT)                    |  |
|  |                                                                             |  |
|  |  [GPIO 25] ---> [Opto-isolated 5V Relay] ---> [230V AC Contactor Coil A1/A2]|  |
|  +-----------------------------------------------------------------------------+  |
|                                                          |                        |
|                                                          v                        |
|                 [ Mains 230V/415V AC ] ---> [ MCB / MPCB ] ---> [ Contactor ]     |
|                                                                    |              |
|                                                                    v              |
|                                                            [ Water Pump Motor ]   |
+-----------------------------------------------------------------------------------+
```

---

## 2. ESP32 Pin Mapping Specification

| ESP32 GPIO Pin | Direction | Signal Name | Description | Signal Characteristics |
| :--- | :--- | :--- | :--- | :--- |
| **GPIO 25** | Output | `RELAY_CTRL` | Motor Start Relay Trigger | 3.3V logic to optocoupler base |
| **GPIO 34** | Input | `E_STOP_BTN` | Hardware Emergency Stop Button | Active LOW, Internal Pullup (Hardware NC) |
| **GPIO 35** | Input | `FLOAT_HIGH` | Tank Overflow Float Switch | Active LOW, Dry Contact Reed Switch |
| **GPIO 32** | Input | `FLOAT_LOW` | Source Sump Dry-Run Switch | Active LOW, Dry Contact Reed Switch |
| **GPIO 33** | ADC (In) | `ADC_WATER_LEVEL`| Hydrostatic Water Level Sensor | 0.5V - 3.3V linear (0 - 100%) |
| **GPIO 39** | ADC (In) | `ADC_TURBIDITY` | Turbidity Sediment Sensor | 0.0V - 3.3V (0 - 30 NTU) |
| **GPIO 36** | ADC (In) | `ADC_CURRENT` | ACS712 / CT Current Sensor | 2.5V center reference, 66-185 mV/A |

---

## 3. Power Supply & Isolation Architecture

1. **Primary Power**: MeanWell HDR-30-5 (5V DC, 3A DIN-rail SMPS) powered by 230V AC mains through a dedicated 2A fuse.
2. **Controller Rail**: 5V DC feeds ESP32 development board VIN (regulated to 3.3V onboard for ESP32 and ADCs).
3. **Galvanic Isolation**:
   - Optocoupler (PC817) between GPIO 25 and 5V Relay coil.
   - Separate flyback diode (1N4007) across relay coil terminals.
   - Snubber circuit (100nF + 100Ω) across contactor coil to suppress inductive kickback.

---

## 4. Bill of Materials (BOM)

### Production Commercial Grade BOM
| Component Item | Part / Model Number | Description | Qty |
| :--- | :--- | :--- | :---: |
| **Microcontroller Unit** | ESP32-WROOM-32D | 32-bit Dual-core MCU, Wi-Fi/BT | 1 |
| **Power Supply Unit** | MeanWell HDR-30-5 | DIN Rail SMPS 5V DC, 3A | 1 |
| **Motor Contactor** | Schneider LC1D09M7 | 3-Pole 220V AC Coil 9A Contactor | 1 |
| **Thermal Overload Relay** | Schneider LRD14 | Adjustable 7-10A Motor Overload | 1 |
| **Circuit Breaker** | Schneider A9F74216 | 2-Pole 16A C-Curve MCB | 1 |
| **Control Relay** | Omron G2R-1-S 5VDC | 1-Pole SPDT 10A Relay with Socket | 1 |
| **Emergency Stop Switch** | Schneider XB4BS542 | 40mm Turn-to-release E-STOP NC | 1 |
| **Water Level Sensor** | Hydrostatic Submersible | 0-5m range, 4-20mA to 0-3.3V converter | 1 |
| **Turbidity Sensor** | DFRobot SEN0189 | Optical turbidity probe with module | 1 |
| **Current Sensor** | Allegro ACS712-20A / CT | Hall-effect current transducer | 1 |
| **Enclosure** | IP65 Polycarbonate Enclosure | 300x200x130mm Weatherproof box | 1 |

---

## 5. Wiring Guidelines & Commissioning Safety
1. Maintain physical separation between High-Voltage AC mains wires and Low-Voltage (3.3V/5V) DC sensor lines.
2. Earth grounding must be solidly connected to the enclosure chassis, pump casing, and breaker earth rail.
3. Test all float switches and E-stop pushbuttons manually before connecting high-voltage motor contactor power.
