from flask import Flask, render_template, render_template_string
import sqlite3
import os
import threading
from mcstatus import JavaServer
from scanner import run_loop
from init_db import init_system

app = Flask(__name__)
# Get DB path from Docker environment, or default to local file
DB_NAME = os.getenv("DB_PATH", "corex.db")

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def get_server_status():
    """Queries the local Minecraft server for status."""
    try:
        server = JavaServer.lookup("localhost:25565", timeout=1)
        status = server.status()
        return f"Online ({status.players.online}/{status.players.max} Players)"
    except Exception:
        return "Offline"

def get_server_era(total_score):
    """
    Calculates the Global Server Rank (Era).
    Tiers:
      - Stone Age: 0 - 4,999
      - Bronze Age: 5,000 - 9,999
      - Iron Age: 10,000 - 24,999
      - Diamond Age: 25,000+
    """
    if total_score >= 25000:
        return {
            "name": "Diamond Age (Max Level)",
            "class_name": "diamond-age",
            "current": total_score,
            "max": 25000,
            "progress": 100
        }
    elif total_score >= 10000:
        min_s = 10000
        max_s = 25000
        progress = int(((total_score - min_s) / (max_s - min_s)) * 100)
        return {
            "name": f"Iron Age ({total_score:,} / {max_s:,} G)",
            "class_name": "iron-age",
            "current": total_score,
            "max": max_s,
            "progress": progress
        }
    elif total_score >= 5000:
        min_s = 5000
        max_s = 10000
        progress = int(((total_score - min_s) / (max_s - min_s)) * 100)
        return {
            "name": f"Bronze Age ({total_score:,} / {max_s:,} G)",
            "class_name": "bronze-age",
            "current": total_score,
            "max": max_s,
            "progress": progress
        }
    else:
        min_s = 0
        max_s = 5000
        progress = int(((total_score - min_s) / (max_s - min_s)) * 100)
        return {
            "name": f"Stone Age ({total_score:,} / {max_s:,} G)",
            "class_name": "stone-age",
            "current": total_score,
            "max": max_s,
            "progress": progress
        }

def get_player_rank(score):
    # Recruit: 0-499
    # Scout: 500-999
    # Veteran: 1000-1999
    # Warlord: 2000+

    if score >= 2000:
        return {
            "current_title": "Warlord",
            "image_path": "static/ranks/warlord.svg",
            "next_title": "Max Rank",
            "progress_percent": 100,
            "current_score": score,
            "next_rank_score": None,
            "min_score": 2000
        }
    elif score >= 1000:
        min_s = 1000
        max_s = 2000
        progress = int(((score - min_s) / (max_s - min_s)) * 100)
        return {
            "current_title": "Veteran",
            "image_path": "static/ranks/veteran.svg",
            "next_title": "Warlord",
            "progress_percent": progress,
            "current_score": score,
            "next_rank_score": max_s,
            "min_score": min_s
        }
    elif score >= 500:
        min_s = 500
        max_s = 1000
        progress = int(((score - min_s) / (max_s - min_s)) * 100)
        return {
            "current_title": "Scout",
            "image_path": "static/ranks/scout.svg",
            "next_title": "Veteran",
            "progress_percent": progress,
            "current_score": score,
            "next_rank_score": max_s,
            "min_score": min_s
        }
    else:
        min_s = 0
        max_s = 500
        progress = int(((score - min_s) / (max_s - min_s)) * 100)
        return {
            "current_title": "Recruit",
            "image_path": "static/ranks/recruit.svg",
            "next_title": "Scout",
            "progress_percent": progress,
            "current_score": score,
            "next_rank_score": max_s,
            "min_score": min_s
        }

@app.route('/')
def index():
    conn = get_db_connection()
    
    # JOIN with players table to get the real name
    query = '''
        SELECT 
            p.gamertag, 
            p.uuid,
            COALESCE(SUM(d.points), 0) as score,
            (SELECT SUM(points) FROM definitions) as total_possible
        FROM players p
        LEFT JOIN unlocks u ON p.uuid = u.player_uuid
        LEFT JOIN definitions d ON u.achievement_id = d.id
        GROUP BY p.uuid
        ORDER BY score DESC
    '''
    players = conn.execute(query).fetchall()
    
    dashboard_data = []
    for p in players:
        # Fetch Total Deaths for Ironman Logic
        death_row = conn.execute(
            "SELECT value FROM player_stats WHERE player_uuid = ? AND stat_name = 'total_deaths'",
            (p['uuid'],)
        ).fetchone()

        deaths = death_row['value'] if death_row else 0

        # Get Unlocked Achievements
        unlocks = conn.execute('''
            SELECT d.id, d.name, d.description, d.icon, u.unlocked_at, d.threshold, d.points
            FROM unlocks u
            JOIN definitions d ON u.achievement_id = d.id
            WHERE u.player_uuid = ?
            ORDER BY u.unlocked_at DESC
        ''', (p['uuid'],)).fetchall()
        
        unlocked_ids = {u['id'] for u in unlocks}

        # Get Progress for Locked Achievements
        # Prepare parameters: First is the UUID, then the list of IDs to exclude
        params = [p['uuid']]
        if unlocked_ids:
            params.extend(unlocked_ids)
        else:
            params.append('') # Dummy value to satisfy the '?' if list is empty

        progress_rows = conn.execute('''
            SELECT d.id, d.name, d.description, d.icon, pp.current_value, d.threshold, d.points
            FROM definitions d
            LEFT JOIN player_progress pp ON d.id = pp.achievement_id AND pp.player_uuid = ?
            WHERE d.id NOT IN ({seq})
        '''.format(seq=','.join(['?']*len(unlocked_ids)) if unlocked_ids else '?'),
        tuple(params)).fetchall()

        processed_unlocks = []
        for u in unlocks:
            processed_unlocks.append({
                "name": u['name'],
                "description": u['description'],
                "icon": u['icon'],
                "unlocked_at": u['unlocked_at'],
                "is_unlocked": True,
                "progress": 100,
                "current": u['threshold'],
                "total": u['threshold'],
                "points": u['points']
            })

        processed_progress = []
        for pr in progress_rows:
            current = pr['current_value'] if pr['current_value'] else 0
            percent = min(100, int((current / pr['threshold']) * 100))
            processed_progress.append({
                "name": pr['name'],
                "description": pr['description'],
                "icon": pr['icon'],
                "is_unlocked": False,
                "progress": percent,
                "current": current,
                "total": pr['threshold'],
                "points": pr['points']
            })

        # Combine, maybe sort by progress?
        # For now, let's just list unlocks first, then progress
        all_achievements = processed_unlocks + processed_progress

        dashboard_data.append({
            "name": p['gamertag'] if p['gamertag'] else p['uuid'][:8],
            "score": p['score'],
            "rank": get_player_rank(p['score']),
            "achievements": all_achievements,
            "deaths": deaths
        })
    
    conn.close()

    # Calculate Global Stats
    global_score = sum(p['score'] for p in dashboard_data)
    server_era = get_server_era(global_score)
    server_status = get_server_status()
    
    return render_template('index.html',
                           data=dashboard_data,
                           server_era=server_era,
                           server_status=server_status)

@app.route('/leaderboard')
def leaderboard():
    conn = get_db_connection()

    def get_top_stat(stat_name, limit=5):
        query = '''
            SELECT p.gamertag, s.value
            FROM player_stats s
            JOIN players p ON s.player_uuid = p.uuid
            WHERE s.stat_name = ?
            ORDER BY s.value DESC
            LIMIT ?
        '''
        return conn.execute(query, (stat_name, limit)).fetchall()

    # 1. Bloodlust (Kills)
    kills = get_top_stat('total_kills')
    bloodlust = [{'rank': i+1, 'name': r['gamertag'], 'score': f"{r['value']:,}"} for i, r in enumerate(kills)]

    # 2. Darwin Awards (Deaths)
    deaths = get_top_stat('total_deaths')
    darwin = [{'rank': i+1, 'name': r['gamertag'], 'score': f"{r['value']:,}"} for i, r in enumerate(deaths)]

    # 3. No Lifers (Play Time: Ticks -> Hours)
    # 20 ticks = 1 sec -> 72000 ticks = 1 hour
    time_rows = get_top_stat('play_time_ticks')
    no_lifers = []
    for i, r in enumerate(time_rows):
        hours = round(r['value'] / 72000, 1)
        no_lifers.append({'rank': i+1, 'name': r['gamertag'], 'score': f"{hours} hrs"})

    # 4. Marathon Runners (Distance: cm -> km)
    # 100 cm = 1 m -> 100,000 cm = 1 km
    dist_rows = get_top_stat('distance_walked')
    runners = []
    for i, r in enumerate(dist_rows):
        km = round(r['value'] / 100000, 2)
        runners.append({'rank': i+1, 'name': r['gamertag'], 'score': f"{km} km"})

    conn.close()

    return render_template('leaderboard.html',
                           bloodlust=bloodlust,
                           darwin=darwin,
                           no_lifers=no_lifers,
                           runners=runners)

def start_scanner():
    """Starts the background scanner thread"""
    scanner_thread = threading.Thread(target=run_loop, daemon=True)
    scanner_thread.start()

if __name__ == '__main__':
    # 1. Initialize Database on Startup
    if not os.path.exists(DB_NAME):
        init_system()
    else:
        # Also run init to ensure schema updates (like new tables) are applied
        init_system()

    # 2. Start the Background Scanner
    start_scanner()

    # 3. Run the Web Server
    app.run(host='0.0.0.0', port=5000)
