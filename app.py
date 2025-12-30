from flask import Flask, render_template, render_template_string, request
import sqlite3
import os
import threading
from mcstatus import JavaServer
from scanner import run_loop
from init_db import init_system
import math

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

def get_player_era(score):
    """
    Calculates the Individual Player Era based on their Score.
    This determines the visual style of their Calling Card.
    """
    if score >= 25000:
        return "diamond-age"
    elif score >= 10000:
        return "iron-age"
    elif score >= 5000:
        return "bronze-age"
    else:
        return "stone-age"

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
    
    # --- 1. Search & Pagination Params ---
    query_param = request.args.get('q', '')
    page_param = request.args.get('page', 1, type=int)
    per_page = 10

    # --- 2. Build Base Query and Count ---
    # Need distinct list of players first based on search
    if query_param:
        count_query = "SELECT COUNT(*) FROM players WHERE gamertag LIKE ?"
        count_args = (f"%{query_param}%",)
    else:
        count_query = "SELECT COUNT(*) FROM players"
        count_args = ()

    total_players = conn.execute(count_query, count_args).fetchone()[0]
    total_pages = math.ceil(total_players / per_page)

    if page_param < 1: page_param = 1
    if page_param > total_pages and total_pages > 0: page_param = total_pages

    offset = (page_param - 1) * per_page

    # --- 3. Fetch Paginated Players ---
    # We need to JOIN/GROUP BY to get score for ordering
    # Note: If we just order by gamertag it's easier, but original code ordered by score DESC.
    # To order by score, we must do the join.

    sql = '''
        SELECT 
            p.gamertag, 
            p.uuid,
            COALESCE(SUM(d.points), 0) as score
        FROM players p
        LEFT JOIN unlocks u ON p.uuid = u.player_uuid
        LEFT JOIN definitions d ON u.achievement_id = d.id
    '''

    if query_param:
        sql += " WHERE p.gamertag LIKE ? "
        sql_args = [f"%{query_param}%"]
    else:
        sql_args = []

    sql += '''
        GROUP BY p.uuid
        ORDER BY score DESC
        LIMIT ? OFFSET ?
    '''
    sql_args.extend([per_page, offset])

    players = conn.execute(sql, tuple(sql_args)).fetchall()
    
    # --- 4. Process Each Player (Details) ---
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
        params = [p['uuid']]
        if unlocked_ids:
            params.extend(unlocked_ids)
        else:
            params.append('') # Dummy

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

        all_achievements = processed_unlocks + processed_progress

        dashboard_data.append({
            "name": p['gamertag'] if p['gamertag'] else p['uuid'][:8],
            "score": p['score'],
            "rank": get_player_rank(p['score']),
            "achievements": all_achievements,
            "deaths": deaths
        })
    
    # --- 5. Global Stats (Need separate query for total server score since we are paginating) ---
    # We can't sum just the paginated results for the Era Bar.
    # We need the sum of ALL players' scores.
    global_score_row = conn.execute('''
        SELECT SUM(score) FROM (
            SELECT COALESCE(SUM(d.points), 0) as score
            FROM players p
            LEFT JOIN unlocks u ON p.uuid = u.player_uuid
            LEFT JOIN definitions d ON u.achievement_id = d.id
            GROUP BY p.uuid
        )
    ''').fetchone()
    global_score = global_score_row[0] if global_score_row and global_score_row[0] else 0

    conn.close()

    server_era = get_server_era(global_score)
    server_status = get_server_status()
    
    return render_template('index.html',
                           data=dashboard_data,
                           server_era=server_era,
                           server_status=server_status,
                           current_page=page_param,
                           total_pages=total_pages,
                           search_query=query_param)

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

@app.route('/player/<uuid>')
def player_profile(uuid):
    conn = get_db_connection()

    # 1. Fetch Player Basic Info & Total Score
    player_row = conn.execute('''
        SELECT
            p.gamertag,
            p.uuid,
            p.last_seen,
            COALESCE(SUM(d.points), 0) as score
        FROM players p
        LEFT JOIN unlocks u ON p.uuid = u.player_uuid
        LEFT JOIN definitions d ON u.achievement_id = d.id
        WHERE p.uuid = ?
        GROUP BY p.uuid
    ''', (uuid,)).fetchone()

    if not player_row:
        conn.close()
        return "Player not found", 404

    # 2. Fetch Stats
    stats_rows = conn.execute('''
        SELECT stat_name, value
        FROM player_stats
        WHERE player_uuid = ?
    ''', (uuid,)).fetchall()

    stats = {row['stat_name']: row['value'] for row in stats_rows}

    # 3. Process Stats
    kills = stats.get('total_kills', 0)
    deaths = stats.get('total_deaths', 0)
    play_time_ticks = stats.get('play_time_ticks', 0)
    distance_cm = stats.get('distance_walked', 0)

    # K/D Ratio
    kd_ratio = round(kills / deaths, 2) if deaths > 0 else kills

    # Playtime (Ticks -> Hours, Minutes)
    # 20 ticks = 1 sec
    total_seconds = play_time_ticks // 20
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    playtime_str = f"{hours}h {minutes}m"

    # Distance (cm -> km)
    distance_km = round(distance_cm / 100000, 2)

    # 4. Fetch Achievements (Unlocked & Locked)
    # Get Unlocked
    unlocks = conn.execute('''
        SELECT d.id, d.name, d.description, d.icon, u.unlocked_at, d.threshold, d.points
        FROM unlocks u
        JOIN definitions d ON u.achievement_id = d.id
        WHERE u.player_uuid = ?
        ORDER BY u.unlocked_at DESC
    ''', (uuid,)).fetchall()

    unlocked_ids = {u['id'] for u in unlocks}

    # Get Locked (Progress)
    # We need to fetch all definitions that are NOT in unlocked_ids
    # AND left join with player_progress

    params = [uuid]
    if unlocked_ids:
        placeholders = ','.join(['?'] * len(unlocked_ids))
        params.extend(list(unlocked_ids))
        query = f'''
            SELECT d.id, d.name, d.description, d.icon, pp.current_value, d.threshold, d.points
            FROM definitions d
            LEFT JOIN player_progress pp ON d.id = pp.achievement_id AND pp.player_uuid = ?
            WHERE d.id NOT IN ({placeholders})
        '''
    else:
        query = '''
            SELECT d.id, d.name, d.description, d.icon, pp.current_value, d.threshold, d.points
            FROM definitions d
            LEFT JOIN player_progress pp ON d.id = pp.achievement_id AND pp.player_uuid = ?
        '''

    progress_rows = conn.execute(query, tuple(params)).fetchall()

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

    all_achievements = processed_unlocks + processed_progress

    # 5. Determine Rank & Era
    score = player_row['score']
    rank_info = get_player_rank(score)
    era_class = get_player_era(score)

    conn.close()

    player_data = {
        "uuid": player_row['uuid'],
        "gamertag": player_row['gamertag'],
        "score": score,
        "rank": rank_info,
        "era_class": era_class,
        "stats": {
            "kills": kills,
            "deaths": deaths,
            "kd": kd_ratio,
            "playtime": playtime_str,
            "distance_km": distance_km
        },
        "achievements": all_achievements
    }

    return render_template('profile.html', player=player_data)

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
