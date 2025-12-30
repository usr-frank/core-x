import os
import json
import sqlite3
import time
from datetime import datetime

# CONFIGURATION
STATS_PATH = os.getenv("MINECRAFT_STATS", os.path.expanduser("~/minecraft/data/world/stats"))
USERCACHE_PATH = os.getenv("MINECRAFT_CACHE", os.path.expanduser("~/minecraft/data/usercache.json"))
DB_NAME = os.getenv("DB_PATH", "corex.db")
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", 5))

def get_db_connection():
    return sqlite3.connect(DB_NAME)

def init_player_table(cursor):
    """Creates the players table on the fly if it doesn't exist"""
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS players (
        uuid TEXT PRIMARY KEY,
        gamertag TEXT,
        last_seen TIMESTAMP
    )
    ''')

def init_stats_table(cursor):
    """Creates the player_stats table on the fly if it doesn't exist"""
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS player_stats (
        player_uuid TEXT,
        stat_name TEXT,
        value INTEGER DEFAULT 0,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (player_uuid, stat_name)
    )
    ''')

def sync_identities(cursor):
    """Reads Minecraft usercache.json to map UUIDs to Names"""
    if not os.path.exists(USERCACHE_PATH):
        # Only print warning once per run or on error, otherwise it spams logs in loop
        # print(f"⚠️  Warning: Usercache not found at {USERCACHE_PATH}")
        return

    try:
        with open(USERCACHE_PATH, 'r') as f:
            users = json.load(f)
            
        # print(f"🆔 Syncing {len(users)} identities...")
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
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Upgrade DB Structure (Safety check)
        init_player_table(cursor)
        init_stats_table(cursor)
        
        # 2. Sync Names
        sync_identities(cursor)
        conn.commit()

        # 3. Get Rules
        cursor.execute("SELECT id, name, threshold, stat_key, icon FROM definitions")
        rules = cursor.fetchall()

        if not os.path.exists(STATS_PATH):
            # print(f"⚠️ Stats path not found: {STATS_PATH}")
            return

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

                # print(f"👤 Scanning: {player_name}")

                # --- GLOBAL STAT HARVEST ---
                global_stats_map = {
                    "minecraft:mob_kills": "total_kills",
                    "minecraft:deaths": "total_deaths",
                    "minecraft:play_one_minute": "play_time_ticks",
                    "minecraft:walk_one_cm": "distance_walked"
                }

                for mc_key, db_key in global_stats_map.items():
                    # Extract value, default to 0
                    stat_val = stats.get(mc_key, 0)

                    cursor.execute('''
                        INSERT INTO player_stats (player_uuid, stat_name, value, last_updated)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(player_uuid, stat_name) DO UPDATE SET
                            value=excluded.value,
                            last_updated=excluded.last_updated
                    ''', (uuid, db_key, stat_val, datetime.now()))
                # ---------------------------
                
                for (rule_id, name, threshold, key, icon) in rules:
                    val = stats.get(key, 0)
                    
                    # Update Progress
                    cursor.execute('''
                        INSERT INTO player_progress (player_uuid, achievement_id, current_value, updated_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(player_uuid, achievement_id) DO UPDATE SET
                            current_value=excluded.current_value,
                            updated_at=excluded.updated_at
                    ''', (uuid, rule_id, val, datetime.now()))

                    # Check Logic for Unlock
                    cursor.execute("SELECT 1 FROM unlocks WHERE player_uuid=? AND achievement_id=?", (uuid, rule_id))
                    if cursor.fetchone(): continue # Skip if done

                    if val >= threshold:
                        print(f"   🏆 UNLOCKED: {name} for {player_name}")
                        cursor.execute("INSERT INTO unlocks (player_uuid, achievement_id) VALUES (?, ?)", (uuid, rule_id))
                        conn.commit()

            except Exception as e:
                print(f"❌ Error scanning {uuid}: {e}")

        conn.commit()
    except Exception as e:
        print(f"❌ Scan Error: {e}")
    finally:
        conn.close()

def run_loop():
    print("🚀 Scanner Loop Initiated")
    while True:
        scan_sector()
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    run_loop()
