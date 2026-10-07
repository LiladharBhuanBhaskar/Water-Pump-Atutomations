# HydraControl — Field Commissioning & QR Code Pairing Workflow
**Phase 26 — Production Device Enrollment Specification (P26-T04)**

---

## 1. Security Architecture & Threat Model

> [!IMPORTANT]
> **ZERO PERMANENT SECRETS IN QR CODE**
> QR codes printed on physical enclosures or device packaging **MUST NEVER** contain permanent MQTT credentials, Wi-Fi passwords, or long-lived API tokens.
> Instead, devices are provisioned at the factory with a **One-Time Enrollment Challenge Token (ECT)** that expires after initial pairing.

### Threats Mitigated:
1. **Device Hijacking**: Prevent unauthorized third parties from scanning an unassigned unit and claiming control.
2. **Cross-Tenant Leakage**: Pairing enforces technician authentication and locks the device UID to the authenticated tenant's organization ID.
3. **Duplicate Pairing / Replay**: Once claimed, the enrollment challenge token is invalidated and cannot be re-used.

---

## 2. Technician Commissioning Flowchart

```
+-----------------------------------------------------------------------------------------+
|                              COMMISSIONING WORKFLOW                                     |
|                                                                                         |
| 1. Physical Mount       2. Scan QR Code         3. Authenticate & Pair  4. Verification |
| +-----------------+    +------------------+    +----------------------+ +-------------+ |
| | Install Contactor|    | Technician scans |    | Backend verifies ECT | | Controller  | |
| | & ESP32 Enclosure|--> | device QR via    |--> | & assigns device to  |-->| sends first | |
| | Connect Sensors  |    | Mobile App UI    |    | Site / Station       | | Heartbeat   | |
| +-----------------+    +------------------+    +----------------------+ +-------------+ |
+-----------------------------------------------------------------------------------------+
```

---

## 3. QR Code Payload Specification

The QR code encodes a signed JSON URI payload:
```json
{
  "device_uid": "HYDRA-ESP32-984A2C",
  "hw_rev": "v2.1",
  "enrollment_token": "ect_7f901c38e4a8b291dc821a4"
}
```

---

## 4. Commissioning Step-by-Step Procedure

1. **Physical Installation**:
   - Mount the IP65 enclosure near the pump station.
   - Connect 230V mains through the MCB and contactor.
   - Connect float switches (Overhead Tank & Sump), current sensor, and level probe to ESP32 terminal blocks.
2. **Technician Mobile App Flow**:
   - Technician logs in using role `technician` or `site_manager`.
   - Opens **Commissioning Tool** -> **Scan Device QR**.
   - Selects target **Organization**, **Site**, and **Station**.
   - Submits `POST /api/v1/devices/commission` with the payload and enrollment token.
3. **Live Handshake Verification**:
   - Device boots up, connects to site Wi-Fi, and connects to MQTT broker using TLS client certificates.
   - First telemetry packet received with `status: ONLINE`.
   - Technician initiates a 5-second **Commissioning Test Run** from the app.
   - Emergency stop is manually pressed to confirm local hardware trip safety.
4. **Sign-off**:
   - Commissioning certificate logged into Audit Trail.
