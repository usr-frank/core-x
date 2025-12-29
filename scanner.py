import os
import json
import sqlite3
from datetime import datetime

# CONFIGURATION
STATS_PATH = os.getenv("MINECRAFT_STATS", os.path.expanduser("~/minecraft/data/world/stats"))
USERCACHE_PATH = os.getenv("MINECRAFT_CACHE", os.path.expanduser("~/minecraft/data/usercache.json"))
DB_NAME = os.getenv("DB_PATH", "corex.db")

def init_player_table(cursor):
    """Creates the players table on the fly if it doesn't exist"""
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS players (
        uuid TEXT PRIMARY KEY,
        gamertag TEXT,
        last_seen TIMESTAMP
    )
    ''')

def sync_identities(cursor):
    """Reads Minecraft usercache.json to map UUIDs to Names"""
    if not os.path.exists(USERCACHE_PATH):
        print(f"⚠️  Warning: Usercache not found at {USERCACHE_PATH}")
        return

    try:
        with open(USERCACHE_PATH, 'r') as f:
            users = json.load(f)
            
        print(f"🆔 Syncing {len(users)} identities...")
        for u in users:
            # Insert or Update the player name
            cursor.execute('''
            INSERT INTO players (uuid, gamertag, last_seen) 
            VALUES (?, ?, ?)
            ON CONFLICT(uuid) DO UPDATE SET gamertag=excluded.gamertag
            ''', (u['uuid'], u['name'], datetime.now()))
            
    except Exception as e:
        print(f"❌ Identity Sync Error: {e}")

def scan_sector():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Upgrade DB Structure
    init_player_table(cursor)
    
    # 2. Sync Names
    sync_identities(cursor)
    conn.commit()
    
    # 3. Get Rules
    cursor.execute("SELECT id, name, threshold, stat_key, icon FROM definitions")
    rules = cursor.fetchall()
    
    files = [f for f in os.listdir(STATS_PATH) if f.endswith(".json")]
    
    for file in files:
        uuid = file.replace(".json", "")
        full_path = os.path.join(STATS_PATH, file)
        
        try:
            with open(full_path, 'r') as f:
                data = json.load(f)
            stats = data.get("stats", {}).get("minecraft:custom", {})
            
            # Fetch Name for logging
            cursor.execute("SELECT gamertag FROM players WHERE uuid=?", (uuid,))
            result = cursor.fetchone()
            player_name = result[0] if result else uuid[:8]
            
            print(f"👤 Scanning: {player_name}")
            
            for (rule_id, name, threshold, key, icon) in rules:
                # Check Logic
                cursor.execute("SELECT 1 FROM unlocks WHERE player_uuid=? AND achievement_id=?", (uuid, rule_id))
                if cursor.fetchone(): continue # Skip if done
                
                val = stats.get(key, 0)
                if val >= threshold:
                    print(f"   🏆 UNLOCKED: {name}")
                    cursor.execute("INSERT INTO unlocks (player_uuid, achievement_id) VALUES (?, ?)", (uuid, rule_id))
                    conn.commit()
                    
        except Exception as e:
            print(f"❌ Error: {e}")

    conn.close()

if __name__ == "__main__":
    scan_sector()
