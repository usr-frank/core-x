from flask import Flask, render_template, render_template_string, request
import sqlite3
import os
import threading
from mcstatus import JavaServer
from scanner import run_loop
from init_db import init_system
import math

app = Flask(__name__)
DB_NAME = os.getenv("DB_PATH", "corex.db")

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def get_server_status():
    try:
        server = JavaServer.lookup("localhost:25565", timeout=1)
        status = server.status()
        return f"Online ({status.players.online}/{status.players.max} Players)"
    except Exception:
        return "Offline"

def get_server_era(total_score):
    if total_score >= 25000:
        return {"name": "Diamond Age (Max Level)", "class_name": "diamond-age", "current": total_score, "max": 25000, "progress": 100}
    elif total_score >= 10000:
        min_s, max_s = 10000, 25000
        progress = int(((total_score - min_s) / (max_s - min_s)) * 100)
        return {"name": f"Iron Age ({total_score:,} / {max_s:,} G)", "class_name": "iron-age", "current": total_score, "max": max_s, "progress": progress}
    elif total_score >= 5000:
        min_s, max_s = 5000, 10000
        progress = int(((total_score - min_s) / (max_s - min_s)) * 100)
        return {"name": f"Bronze Age ({total_score:,} / {max_s:,} G)", "class_name": "bronze-age", "current": total_score, "max": max_s, "progress": progress}
    else:
        min_s, max_s = 0, 5000
        progress = int(((total_score - min_s) / (max_s - min_s)) * 100)
        return {"name": f"Stone Age ({total_score:,} / {max_s:,} G)", "class_name": "stone-age", "current": total_score, "max": max_s, "progress": progress}

def get_player_era(score):
    if score >= 25000: return "diamond-age"
    elif score >= 10000: return "iron-age"
    elif score >= 5000: return "bronze-age"
    else: return "stone-age"

def get_player_rank(score):
    if score >= 2000:
        return {"current_title": "Warlord", "image_path": "static/ranks/warlord.svg", "next_title": "Max Rank", "progress_percent": 100, "current_score": score, "next_rank_score": None}
    elif score >= 1000:
        progress = int(((score - 1000) / 1000) * 100)
        return {"current_title": "Veteran", "image_path": "static/ranks/veteran.svg", "next_title": "Warlord", "progress_percent": progress, "current_score": score, "next_rank_score": 2000}
    elif score >= 500:
        progress = int(((score - 500) / 500) * 100)
        return {"current_title": "Scout", "image_path": "static/ranks/scout.svg", "next_title": "Veteran", "progress_percent": progress, "current_score": score, "next_rank_score": 1000}
    else:
        progress = int((score / 500) * 100)
        return {"current_title": "Recruit", "image_path": "static/ranks/recruit.svg", "next_title": "Scout", "progress_percent": progress, "current_score": score, "next_rank_score": 500}

@app.route('/')
def index():
    conn = get_db_connection()
    query_param = request.args.get('q', '')
    page_param = request.args.get('page', 1, type=int)
    per_page = 10

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

    sql = '''
        SELECT p.gamertag, p.uuid, COALESCE(SUM(d.points), 0) as score
        FROM players p
        LEFT JOIN unlocks u ON p.uuid = u.player_uuid
        LEFT JOIN definitions d ON u.achievement_id = d.id
    '''
    sql_args = []
    if query_param:
        sql += " WHERE p.gamertag LIKE ? "
        sql_args.append(f"%{query_param}%")
    
    sql += " GROUP BY p.uuid ORDER BY score DESC LIMIT ? OFFSET ? "
    sql_args.extend([per_page, offset])

    players = conn.execute(sql, tuple(sql_args)).fetchall()
    
    dashboard_data = []
    for p in players:
        death_row = conn.execute("SELECT value FROM player_stats WHERE player_uuid = ? AND stat_name = 'total_deaths'", (p['uuid'],)).fetchone()
        deaths = death_row['value'] if death_row else 0
        
        unlocks = conn.execute('''
            SELECT d.id, d.name, d.description, d.icon, u.unlocked_at, d.threshold, d.points
            FROM unlocks u JOIN definitions d ON u.achievement_id = d.id
            WHERE u.player_uuid = ? ORDER BY u.unlocked_at DESC
        ''', (p['uuid'],)).fetchall()
        unlocked_ids = {u['id'] for u in unlocks}
        
        params = [p['uuid']]
        if unlocked_ids: params.extend(unlocked_ids)
        else: params.append('')
        
        progress_rows = conn.execute(f'''
            SELECT d.id, d.name, d.description, d.icon, pp.current_value, d.threshold, d.points
            FROM definitions d
            LEFT JOIN player_progress pp ON d.id = pp.achievement_id AND pp.player_uuid = ?
            WHERE d.id NOT IN ({','.join(['?']*len(unlocked_ids)) if unlocked_ids else '?'})
        ''', tuple(params)).fetchall()

        all_achievements = []
        for u in unlocks:
            all_achievements.append({"name": u['name'], "description": u['description'], "icon": u['icon'], "unlocked_at": u['unlocked_at'], "is_unlocked": True, "progress": 100, "current": u['threshold'], "total": u['threshold'], "points": u['points']})
        for pr in progress_rows:
            current = pr['current_value'] if pr['current_value'] else 0
            percent = min(100, int((current / pr['threshold']) * 100))
            all_achievements.append({"name": pr['name'], "description": pr['description'], "icon": pr['icon'], "is_unlocked": False, "progress": percent, "current": current, "total": pr['threshold'], "points": pr['points']})

        dashboard_data.append({
            "uuid": p['uuid'],  # <--- FIXED: Added UUID so the template can link to it
            "name": p['gamertag'] if p['gamertag'] else p['uuid'][:8],
            "score": p['score'],
            "rank": get_player_rank(p['score']),
            "achievements": all_achievements,
            "deaths": deaths
        })
    
    global_score_row = conn.execute("SELECT SUM(score) FROM (SELECT COALESCE(SUM(d.points), 0) as score FROM players p LEFT JOIN unlocks u ON p.uuid = u.player_uuid LEFT JOIN definitions d ON u.achievement_id = d.id GROUP BY p.uuid)").fetchone()
    global_score = global_score_row[0] if global_score_row and global_score_row[0] else 0

    conn.close()
    return render_template('index.html', data=dashboard_data, server_era=get_server_era(global_score), server_status=get_server_status(), current_page=page_param, total_pages=total_pages, search_query=query_param)

@app.route('/leaderboard')
def leaderboard():
    conn = get_db_connection()
    def get_top(stat): return conn.execute("SELECT p.gamertag, s.value FROM player_stats s JOIN players p ON s.player_uuid = p.uuid WHERE s.stat_name = ? ORDER BY s.value DESC LIMIT 5", (stat,)).fetchall()
    
    bloodlust = [{'rank': i+1, 'name': r['gamertag'], 'score': f"{r['value']:,}"} for i, r in enumerate(get_top('total_kills'))]
    darwin = [{'rank': i+1, 'name': r['gamertag'], 'score': f"{r['value']:,}"} for i, r in enumerate(get_top('total_deaths'))]
    no_lifers = [{'rank': i+1, 'name': r['gamertag'], 'score': f"{round(r['value']/72000, 1)} hrs"} for i, r in enumerate(get_top('play_time_ticks'))]
    runners = [{'rank': i+1, 'name': r['gamertag'], 'score': f"{round(r['value']/100000, 2)} km"} for i, r in enumerate(get_top('distance_walked'))]
    conn.close()
    return render_template('leaderboard.html', bloodlust=bloodlust, darwin=darwin, no_lifers=no_lifers, runners=runners)

@app.route('/player/<uuid>')
def player_profile(uuid):
    conn = get_db_connection()
    player_row = conn.execute("SELECT p.gamertag, p.uuid, COALESCE(SUM(d.points), 0) as score FROM players p LEFT JOIN unlocks u ON p.uuid = u.player_uuid LEFT JOIN definitions d ON u.achievement_id = d.id WHERE p.uuid = ? GROUP BY p.uuid", (uuid,)).fetchone()
    
    if not player_row:
        conn.close()
        return "Player not found", 404

    stats_rows = conn.execute("SELECT stat_name, value FROM player_stats WHERE player_uuid = ?", (uuid,)).fetchall()
    stats = {row['stat_name']: row['value'] for row in stats_rows}
    
    kills = stats.get('total_kills', 0)
    deaths = stats.get('total_deaths', 0)
    kd = round(kills / deaths, 2) if deaths > 0 else kills
    
    unlocks = conn.execute("SELECT d.id, d.name, d.description, d.icon, u.unlocked_at, d.threshold, d.points FROM unlocks u JOIN definitions d ON u.achievement_id = d.id WHERE u.player_uuid = ? ORDER BY u.unlocked_at DESC", (uuid,)).fetchall()
    unlocked_ids = {u['id'] for u in unlocks}
    
    params = [uuid]
    if unlocked_ids: params.extend(list(unlocked_ids))
    else: params.append('')
    
    progress_rows = conn.execute(f"SELECT d.id, d.name, d.description, d.icon, pp.current_value, d.threshold, d.points FROM definitions d LEFT JOIN player_progress pp ON d.id = pp.achievement_id AND pp.player_uuid = ? WHERE d.id NOT IN ({','.join(['?']*len(unlocked_ids)) if unlocked_ids else '?'})", tuple(params)).fetchall()
    
    all_achievements = []
    for u in unlocks: all_achievements.append({"name": u['name'], "description": u['description'], "icon": u['icon'], "unlocked_at": u['unlocked_at'], "is_unlocked": True, "progress": 100, "current": u['threshold'], "total": u['threshold'], "points": u['points']})
    for pr in progress_rows:
        current = pr['current_value'] if pr['current_value'] else 0
        percent = min(100, int((current / pr['threshold']) * 100))
        all_achievements.append({"name": pr['name'], "description": pr['description'], "icon": pr['icon'], "is_unlocked": False, "progress": percent, "current": current, "total": pr['threshold'], "points": pr['points']})

    score = player_row['score']
    conn.close()
    
    return render_template('profile.html', player={
        "uuid": player_row['uuid'], "gamertag": player_row['gamertag'], "score": score,
        "rank": get_player_rank(score), "era_class": get_player_era(score),
        "stats": {"kills": kills, "deaths": deaths, "kd": kd, "playtime": f"{stats.get('play_time_ticks',0)//72000}h {(stats.get('play_time_ticks',0)%3600)//60}m"},
        "achievements": all_achievements
    })

if __name__ == '__main__':
    if not os.path.exists(DB_NAME): init_system()
    else: init_system()
    threading.Thread(target=run_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
