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

def init_tables(cursor):
    """Creates necessary tables on the fly if they don't exist"""
    # 1. Players Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS players (
        uuid TEXT PRIMARY KEY,
        gamertag TEXT,
        last_seen TIMESTAMP
    )
    ''')
    # 2. Player Stats Table (For Leaderboards)
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
        return

    try:
        with open(USERCACHE_PATH, 'r') as f:
            users = json.load(f)
            
        for u in users:
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
        init_tables(cursor)
        
        # 2. Sync Names
        sync_identities(cursor)
        conn.commit()

        # 3. Get Rules for Achievements
        cursor.execute("SELECT id, name, threshold, stat_key, icon FROM definitions")
        rules = cursor.fetchall()

        if not os.path.exists(STATS_PATH):
            return

        files = [f for f in os.listdir(STATS_PATH) if f.endswith(".json")]

        for file in files:
            uuid = file.replace(".json", "")
            full_path = os.path.join(STATS_PATH, file)
            
            try:
                with open(full_path, 'r') as f:
                    data = json.load(f)
                
                # --- PART A: GLOBAL STAT HARVEST (For Leaderboards) ---
                custom_stats = data.get("stats", {}).get("minecraft:custom", {})
                
                # 1. Mob Kills (Handle missing key)
                total_kills = custom_stats.get("minecraft:mob_kills", 0)
                # 2. Deaths (Handle missing key)
                total_deaths = custom_stats.get("minecraft:deaths", 0)
                # 3. Play Time (FIXED KEY: play_time instead of play_one_minute)
                play_time = custom_stats.get("minecraft:play_time", 0)
                # 4. Walk Distance
                dist_walked = custom_stats.get("minecraft:walk_one_cm", 0)

                harvest_data = [
                    (uuid, 'total_kills', total_kills),
                    (uuid, 'total_deaths', total_deaths),
                    (uuid, 'play_time_ticks', play_time),
                    (uuid, 'distance_walked', dist_walked)
                ]

                cursor.executemany('''
                    INSERT INTO player_stats (player_uuid, stat_name, value, last_updated)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(player_uuid, stat_name) DO UPDATE SET
                        value=excluded.value,
                        last_updated=excluded.last_updated
                ''', [(h[0], h[1], h[2], datetime.now()) for h in harvest_data])

                # --- PART B: ACHIEVEMENT SCANNING ---
                # Fetch Name for logging
                cursor.execute("SELECT gamertag FROM players WHERE uuid=?", (uuid,))
                result = cursor.fetchone()
                player_name = result[0] if result else uuid[:8]
                
                # Need to look at ROOT stats for accurate mining/crafting checks
                # Helper to find deeply nested keys safely
                def get_stat_value(stat_path):
                    parts = stat_path.split(":")
                    # e.g. minecraft:mined:minecraft:stone -> ["minecraft", "mined", "minecraft", "stone"]
                    # But JSON structure is stats -> minecraft:mined -> minecraft:stone
                    # We need to map the DB key format to the JSON format
                    
                    # Case 1: Custom Stats (minecraft:mob_kills)
                    if len(parts) == 2: 
                        return custom_stats.get(stat_path, 0)
                    
                    # Case 2: Block/Item Stats (minecraft:mined:minecraft:stone)
                    # The DB key is often "minecraft:mined:minecraft:stone"
                    # The JSON is data["stats"]["minecraft:mined"]["minecraft:stone"]
                    category = parts[0] + ":" + parts[1] # "minecraft:mined"
                    item = parts[2] + ":" + parts[3]     # "minecraft:stone"
                    
                    return data.get("stats", {}).get(category, {}).get(item, 0)

                for (rule_id, name, threshold, key, icon) in rules:
                    # Use the helper to find the value regardless of category
                    val = get_stat_value(key)
                    
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
