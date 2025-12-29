import sqlite3
import os
import yaml

# FIX: Use the Environment Variable just like app.py does
DB_NAME = os.getenv("DB_PATH", "corex.db")
ACHIEVEMENTS_PATH = "achievements.yaml"

def init_system():
    # Connect to (or create) the database file
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    print(f"⚙️  Initializing Core-X Database at {DB_NAME}...")

    # 1. Create Table: DEFINITIONS (The Rules)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS definitions (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        stat_key TEXT NOT NULL,
        threshold INTEGER NOT NULL,
        icon TEXT
    )
    ''')
    
    # 2. Create Table: UNLOCKS (The Save Data)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS unlocks (
        player_uuid TEXT,
        achievement_id TEXT,
        unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (player_uuid, achievement_id),
        FOREIGN KEY(achievement_id) REFERENCES definitions(id)
    )
    ''')
    
    # 3. Create Table: PLAYERS (Identity)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS players (
        uuid TEXT PRIMARY KEY,
        gamertag TEXT,
        last_seen TIMESTAMP
    )
    ''')

    # 4. Create Table: PLAYER_PROGRESS (Progress Tracking)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS player_progress (
        player_uuid TEXT,
        achievement_id TEXT,
        current_value INTEGER DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (player_uuid, achievement_id),
        FOREIGN KEY(achievement_id) REFERENCES definitions(id)
    )
    ''')

    # 5. Seed Initial Data from YAML
    if os.path.exists(ACHIEVEMENTS_PATH):
        print(f"📄 Loading achievements from {ACHIEVEMENTS_PATH}...")
        with open(ACHIEVEMENTS_PATH, 'r') as f:
            data = yaml.safe_load(f)

        achievements_data = []
        for ach in data.get('achievements', []):
            achievements_data.append((
                ach['id'],
                ach['name'],
                ach['description'],
                ach['stat_key'],
                ach['threshold'],
                ach['icon']
            ))

        cursor.executemany('''
        INSERT INTO definitions (id, name, description, stat_key, threshold, icon)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            description=excluded.description,
            stat_key=excluded.stat_key,
            threshold=excluded.threshold,
            icon=excluded.icon
        ''', achievements_data)
    else:
        print(f"⚠️  Warning: {ACHIEVEMENTS_PATH} not found. Skipping seed.")

    conn.commit()
    conn.close()
    print("✅ Database System Online.")

if __name__ == "__main__":
    init_system()
