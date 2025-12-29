import sqlite3
import os

# FIX: Use the Environment Variable just like app.py does
DB_NAME = os.getenv("DB_PATH", "corex.db")

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

    # 4. Seed Initial Data
    achievements = [
        ("FIRST_BLOOD", "You Died.", "Succumb to the harsh reality.", "minecraft:deaths", 1, "💀"),
        ("GRAVITY_TESTER", "Leg Day", "Jump 10 times.", "minecraft:jump", 10, "🦘"),
        ("TIME_TRAVELER", "Survivor", "Play for 1 full day (20 mins).", "minecraft:play_time", 24000, "⏳")
    ]
    
    cursor.executemany('''
    INSERT OR IGNORE INTO definitions (id, name, description, stat_key, threshold, icon)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', achievements)

    conn.commit()
    conn.close()
    print("✅ Database System Online.")

if __name__ == "__main__":
    init_system()
