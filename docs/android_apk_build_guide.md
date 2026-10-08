# HydraControl — Android APK Generation & Mobile Installation Guide

This document explains how to build, package, and install the **HydraControl Smart Water Pump Mobile Application** on Android devices.

---

## 1. Fast Method: Instant PWA Install on Any Android Device (Zero Build Tools Needed)

HydraControl includes full Progressive Web App (PWA) manifest support (`manifest.json`), touch optimizations, and standalone portrait mode.

### Steps:
1. Open Google Chrome on your Android mobile device.
2. Navigate to your HydraControl URL (e.g. `http://<your-server-ip>:5173` or your production domain).
3. Tap the **Three Dots Menu (⋮)** in the top-right corner of Chrome.
4. Tap **"Add to Home screen"** or **"Install App"**.
5. HydraControl will be installed as a standalone Android application with its own app icon and splash screen, running in full-screen mode without browser address bars!

---

## 2. Native Android APK Build (Using Capacitor & Android Studio)

To compile a standalone `.apk` or `.aab` file for distribution or sideloading onto Android phones:

### Prerequisites:
- Node.js 18+ & npm
- Android Studio with Android SDK installed

### Step-by-Step APK Generation:

#### 1. Build the Frontend Production Assets
In your terminal, navigate to the `frontend` directory and build the production bundle:
```bash
cd frontend
npm run build
```

#### 2. Install Capacitor Dependencies
```bash
npm install @capacitor/core @capacitor/cli @capacitor/android
```

#### 3. Initialize Capacitor Configuration
Create `capacitor.config.json` in `frontend/`:
```json
{
  "appId": "io.hydracontrol.app",
  "appName": "HydraControl",
  "webDir": "dist",
  "bundledWebRuntime": false,
  "server": {
    "cleartext": true
  }
}
```

#### 4. Add Android Platform & Sync
```bash
npx cap add android
npx cap sync
```

#### 5. Open & Build APK in Android Studio
```bash
npx cap open android
```
In Android Studio:
- Select **Build** > **Build Bundle(s) / APK(s)** > **Build APK(s)**.
- Once finished, click **locate** to find your output `app-debug.apk` in `android/app/build/outputs/apk/debug/`.
- Transfer the `.apk` file to any Android device and tap to install!

---

## 3. UI Overview for Operators (User Mode)

The mobile APK interface provides an ultra-clean, one-touch water pump management experience:

1. 🟢 **START PUMP**: Big glowing emerald button to start the pump with live animated wave water level indicator.
2. 🔴 **STOP PUMP**: Big glowing red emergency-stop button for immediate pump shutdown.
3. 📅 **SCHEDULES**: One-tap access to set automated daily timer schedules and durations.
4. 💧 **Visual Water Tank Gauge**: Live % fill level with overhead tank and sump volume indicators.
5. 🛡️ **Autonomous Safety Protection**: Real-time water purity (Turbidity NTU) and electrical current monitoring.
