# Core-X // Vanguard Protocol

![Platform](https://img.shields.io/badge/Platform-Docker-blue?logo=docker&logoColor=white)
![Status](https://img.shields.io/badge/Status-Operational-brightgreen)

> **Next-Gen Achievement Tracking for Minecraft Java Edition**

Core-X is a Dockerized Sidecar application that attaches to your Minecraft server, reads player statistics in real-time, and generates a persistent achievement dashboard.

## 📡 Features
* **Zero Lag:** Runs completely outside the game process.
* **Persistence:** Uses SQLite to store achievements forever.
* **Identity:** Automatically syncs UUIDs to GamerTags.
* **Web Dashboard:** Dark-mode UI to view leaderboards.

## 🛠 Installation

### 1. Clone the Relay
```bash
git clone https://github.com/usr-frank/core-x.git
cd core-x
```

### 2. Configure Paths
Edit `docker-compose.yml` to point to your Minecraft server data folder:
```yaml
volumes:
  - /path/to/your/minecraft/world/stats:/data/stats:ro
  - /path/to/your/minecraft/usercache.json:/data/usercache.json:ro
```

### 3. Ignite
```bash
docker compose up -d --build
```

### 4. Verify
Access the dashboard at: `http://localhost:5000`

## 🏆 Default Achievements
* **First Blood:** Die once.
* **Leg Day:** Jump 10 times.
* **Survivor:** Play for 24,000 ticks (1 day).

---
*Powered by Python, Flask, and SQLite.*
