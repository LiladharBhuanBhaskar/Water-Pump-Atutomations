# 🚀 HydraControl — Production Deployment & Operations Guide

This comprehensive guide outlines how to deploy, configure, and maintain the **HydraControl Commercial IoT Platform** across self-hosted servers, cloud virtual private servers (AWS, DigitalOcean, Hetzner), container environments, and connect live ESP32 hardware.

---

## 🏗️ 1. Architecture Overview

```
                          Internet / Users
                                 │
                     [ HTTPS / Port 80 & 443 ]
                                 ▼
                     ┌───────────────────────┐
                     │     Nginx Gateway     │  (SSL Termination, SPA Routing,
                     │  (Frontend Container) │   Gzip & WebSocket Upgrades)
                     └───────────┬───────────┘
                                 │
           ┌─────────────────────┴─────────────────────┐
           ▼                                           ▼
  ┌─────────────────┐                        ┌───────────────────┐
  │  FastAPI Server │ ◄── [ Pub/Sub MQTT ] ──►  Mosquitto Broker │
  │  & Schedulers   │                        │   (Port 1883/8883)│
  └────────┬────────┘                        └─────────▲─────────┘
           │                                           │
  ┌────────▼────────┐                                  │ [ WiFi / TLS ]
  │ PostgreSQL / DB │                                  ▼
  │  (Persistent)   │                        ┌───────────────────┐
  └─────────────────┘                        │ ESP32 Controllers │
                                             │ (Pumps & Sensors) │
                                             └───────────────────┘
```

---

## ⚡ 2. Quick Start: Single-Command Docker Deployment

To launch the full production stack (FastAPI Backend + React Frontend + Nginx + Mosquitto MQTT Broker + PostgreSQL Database) in a single command:

### Prerequisites:
- **Docker** (`>= 24.0`)
- **Docker Compose** (`>= 2.20`)

### Step 1: Clone Repository
```bash
git clone https://github.com/LiladharBhuanBhaskar/Water-Pump-Atutomations.git
cd Water-Pump-Atutomations
```

### Step 2: Configure Production Environment Variables
```bash
cp .env.example .env
```
Edit `.env` to set your custom secret key:
```env
ENVIRONMENT=production
SECRET_KEY=generate_a_secure_random_64_character_hex_key_here
POSTGRES_PASSWORD=your_secure_db_password
ADMIN_EMAIL=admin@yourcompany.com
ADMIN_PASSWORD=YourStrongPassword123!
```

### Step 3: Build & Launch Stack
```bash
docker compose up -d --build
```

### Step 4: Verify Health & Running Containers
```bash
docker compose ps
```
The services will start:
- **Web App & Admin Console**: `http://your-server-ip/`
- **Backend API & OpenAPI Docs**: `http://your-server-ip/docs`
- **MQTT Broker**: `your-server-ip:1883`

---

## ☁️ 3. Deploying to Cloud VPS (Ubuntu 22.04 / 24.04 LTS)

Follow these steps for deploying on **DigitalOcean Droplet, AWS EC2, Linode, or Hetzner**:

### 1. Install Docker & Docker Compose
```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg ufw

# Install Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 2. Configure Firewall (UFW)
```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp     # HTTP (Web & API)
sudo ufw allow 443/tcp    # HTTPS (SSL)
sudo ufw allow 1883/tcp   # MQTT Broker (ESP32 Device Connections)
sudo ufw enable
```

### 3. Deploy Stack
```bash
git clone https://github.com/LiladharBhuanBhaskar/Water-Pump-Atutomations.git /opt/hydracontrol
cd /opt/hydracontrol
docker compose up -d --build
```

---

## 🔒 4. Free SSL / HTTPS Setup with Let's Encrypt & Certbot

To enable HTTPS and secure WebSockets (`wss://`):

### 1. Install Certbot
```bash
sudo apt-get install -y certbot python3-certbot-nginx
```

### 2. Issue Certificate
```bash
sudo certbot certonly --standalone -d hydra.yourdomain.com
```

### 3. Mount SSL Certificates in Nginx
Add certificates to `docker-compose.yml` volumes for `frontend`:
```yaml
volumes:
  - /etc/letsencrypt:/etc/letsencrypt:ro
```
And update `infra/docker/nginx.conf` to listen on `443 ssl`.

---

## 🎛️ 5. ESP32 Hardware Connection Guide

To connect physical ESP32 controllers to your production deployment:

1. Open [`firmware/include/config.h`](file:///c:/Users/bhask/OneDrive/Desktop/water%20pump%20automations/firmware/include/config.h) in PlatformIO or Arduino IDE:
```cpp
// Set your Wi-Fi credentials
#define WIFI_SSID "Your_Facility_WiFi"
#define WIFI_PASSWORD "Your_WiFi_Password"

// Set your deployed server's domain or IP
#define MQTT_BROKER "your-server-ip-or-domain.com"
#define MQTT_PORT 1883

// Device Hardware Identifier
#define DEVICE_UID "HYDRA-PROD-ESP32-001"
```

2. Flash the firmware to ESP32:
```bash
pio run --target upload
```

3. View Serial Monitor:
```bash
pio device monitor
```
The controller will automatically connect to Wi-Fi, register with Mosquitto, and begin streaming real-time tank levels and accepting motor commands.

---

## 🛠️ 6. Useful Operations & Maintenance Commands

### View Live Logs
```bash
# Backend logs
docker compose logs -f backend

# MQTT broker logs
docker compose logs -f mqtt_broker

# Frontend / Nginx access logs
docker compose logs -f frontend
```

### Database Backup (PostgreSQL)
```bash
docker compose exec postgres pg_dump -U postgres hydracontrol > hydracontrol_backup_$(date +%Y%m%d).sql
```

### Database Restore
```bash
cat hydracontrol_backup.sql | docker compose exec -T postgres psql -U postgres -d hydracontrol
```

### Restart Entire Service Stack
```bash
docker compose restart
```

---

## 🔐 7. Production Default Credentials

| Service | Endpoint | Default Username / Email | Default Password |
| :--- | :--- | :--- | :--- |
| **Web Dashboard** | `http://<host>/` | `admin@hydracontrol.io` | `SecretPass123!` |
| **Operator Access**| `http://<host>/` | `operator@hydracontrol.io` | `SecretPass123!` |
| **PostgreSQL Database** | `localhost:5432` | `postgres` | `postgrespassword` (in `.env`) |
| **Mosquitto MQTT** | `<host>:1883` | Anonymous (or configure auth) | N/A |

> [!IMPORTANT]
> Change the default admin password immediately upon first login via the **Admin Console** or profile settings.
