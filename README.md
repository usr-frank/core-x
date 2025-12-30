# Core-X // Vanguard Protocol

![Platform](https://img.shields.io/badge/Platform-Docker-blue?logo=docker&logoColor=white)
![Status](https://img.shields.io/badge/Status-Operational-brightgreen)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

> **Next-Gen Achievement Tracking for Minecraft Java Edition**

Core-X is a Dockerized Sidecar application that attaches to your Minecraft server, reads player statistics in real-time, and generates a persistent achievement dashboard.

## 📡 Features
* **Zero Lag:** Runs completely outside the game process.
* **Persistence:** Uses SQLite to store achievements forever.
* **Identity:** Automatically syncs UUIDs to GamerTags.
* **Web Dashboard:** Dark-mode UI with live progress tracking.
* **Configurable:** Define custom achievements via YAML.
* **Community Hub:** Real-time Server Status and Global "Age" Progression system.
* **Visual Flair:** Rank Emblems and a "Nether/Aether" Theme Switcher.
* **Hall of Fame:** A Leaderboard system tracking top stats.

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

### 3. Customize Achievements
Edit `achievements.yaml` to define your own rules.
```yaml
achievements:
  - id: MINER_69er
    name: "It's Honest Work"
    description: "Mine 1,000 Stone."
    stat_key: "minecraft:mined:minecraft:stone"
    threshold: 1000
    icon: "⛏️"
    points: 50
```
*Note: If `points` is omitted, it defaults to 50 G.*

### 4. Player Ranks & Battle Pass
Players are assigned a rank based on their Total Gamerscore, visualized with a gold progress bar and a unique rank emblem:
* **Recruit:** 0 - 499 G
* **Scout:** 500 - 999 G
* **Veteran:** 1000 - 1999 G
* **Warlord:** 2000+ G (Max Rank)

*Note: This feature requires rank SVG assets (`recruit.svg`, `scout.svg`, `veteran.svg`, `warlord.svg`) to be present in `static/ranks/`.*

### 5. Theme Switcher (Phase 2)
Users can now toggle between two visual themes, persisted locally:
* **Nether Mode:** The classic Dark theme with green accents.
* **Aether Mode:** A new Light theme with white cards and blue accents.

### 6. Community Hub & Leaderboard (Phase 3)
* **Global Ages:** Track server progress from Stone Age to Diamond Age.
* **Server Status:** See online/offline status and player count.
* **Leaderboard:** A dedicated Hall of Fame page (`/leaderboard`) tracking Top 5 in:
    * **Bloodlust:** Most Kills.
    * **Darwin Awards:** Most Deaths.
    * **No Lifers:** Longest Playtime (Hours).
    * **Marathon Runners:** Longest Distance Walked (km).
* **Ironman Status:** Players on the dashboard display a ❤️ if they have 0 deaths, or a 💀 if they have fallen.

### 7. Player Profiles (Phase 5)
Core-X now features detailed **Player Profiles ("The Barracks")**.
* **Calling Cards:** Dynamic profile banners based on the player's personal "Era" (Stone, Bronze, Iron, Diamond).
* **Combat Record:** Detailed stats grid showing K/D, Kills, Deaths, and Playtime.
* **Full History:** A complete list of all unlocked and locked achievements with progress bars.

### 8. Ignite
```bash
docker compose up -d --build
```

### 9. Verify
Access the dashboard at: `http://localhost:5000`

## 🏆 Default Achievements
* **First Blood:** Die once.
* **Leg Day:** Jump 10 times.
* **Survivor:** Play for 24,000 ticks (1 day).

## 📜 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
*Powered by Python, Flask, and SQLite.*
