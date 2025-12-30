# Core-X // Vanguard Protocol

![Platform](https://img.shields.io/badge/Platform-Docker-blue?logo=docker&logoColor=white)
![Status](https://img.shields.io/badge/Status-Operational-brightgreen)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

> **Next-Gen Achievement Tracking for Minecraft Java Edition**

Core-X is a robust, Dockerized "sidecar" application for Minecraft servers. It parses statistics directly from the disk in real-time to generate a persistent, high-performance web dashboard featuring achievements, rankings, and deep player analytics—all without impacting server TPS.

## 📡 Features

*   **Zero-Overhead Parsing:** Reads `stats/*.json` directly from disk. No plugins or RCON required.
*   **Production-Grade Serving:** Powered by **Gunicorn** for high concurrency and stability.
*   **Persistent Data:** SQLite backend ensures history is kept even if map files are reset (ideal for seasonal servers).
*   **Cyberpunk UI:** A visually striking "Nether" (Dark) and "Aether" (Light) theme system.
*   **Leaderboards:** "Hall of Fame" tracking Kills, Deaths, Playtime, and Distance.
*   **Economy System:** Auto-calculates "Net Worth" based on mined ores (Diamonds, Debris, Gold, etc.).
*   **Rank System:** Auto-promotes players from Recruit to Warlord based on Achievement Points (Gamerscore).

## 🛠 Deployment

Core-X is designed to run alongside your Minecraft server using Docker Compose.

### Prerequisites

*   Docker & Docker Compose
*   Access to the Minecraft server's `world/stats` directory.

### Quick Start

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/yourusername/core-x.git
    cd core-x
    ```

2.  **Configure `docker-compose.yml`**
    Map the volumes to your actual Minecraft server paths:
    ```yaml
    volumes:
      - /path/to/minecraft/world/stats:/data/stats:ro
      - /path/to/minecraft/usercache.json:/data/usercache.json:ro
    ```

3.  **Launch**
    ```bash
    docker compose up -d --build
    ```

4.  **Verify**
    *   Dashboard: `http://localhost:5000`
    *   Health Check: `http://localhost:5000/health`

## ⚙️ Configuration

### Achievements (`achievements.yaml`)
Define custom achievements in `achievements.yaml`. The system watches this file for changes (restart required to re-seed DB definitions).

```yaml
achievements:
  - id: KILL_ZOMBIE
    name: "Walking Dead"
    description: "Kill 100 Zombies"
    stat_key: "minecraft:killed:minecraft:zombie"
    threshold: 100
    points: 25
    icon: "🧟"
```

### Environment Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `MINECRAFT_STATS` | Path to stats directory (inside container) | `/data/stats` |
| `MINECRAFT_CACHE` | Path to usercache.json (inside container) | `/data/usercache.json` |
| `DB_PATH` | SQLite database location | `/data/corex.db` |
| `SCAN_INTERVAL` | Seconds between stat updates | `5` |

## 🏗 Architecture

Core-X uses a split-process architecture within a single container:

1.  **Scanner Process:** A background Python thread that continuously parses JSON files from the Minecraft disk, updating the SQLite database.
2.  **Web Server:** A Gunicorn WSGI server handling HTTP requests, rendering Jinja2 templates, and serving the frontend.
3.  **Database:** A shared SQLite file (`corex.db`) acting as the persistent state store.

## 🛡 Security & Networking

*   **Public Access:** This application is designed to be read-only and publicly accessible.
*   **Port Forwarding:** Can be safely exposed via Port 5000 (standard web traffic).
*   **Health Checks:** Use the `/health` endpoint for uptime monitoring (e.g., Uptime Kuma).

## 🏆 Ranks

Players earn **Gamerscore (G)** by completing achievements.

*   **Recruit:** 0 - 499 G
*   **Scout:** 500 - 999 G
*   **Veteran:** 1,000 - 1,999 G
*   **Warlord:** 2,000+ G

## 📜 License

MIT License. Free to use for any Minecraft community.
