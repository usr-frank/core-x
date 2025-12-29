from flask import Flask, render_template, render_template_string
import sqlite3
import os
import threading
from scanner import run_loop
from init_db import init_system

app = Flask(__name__)
# Get DB path from Docker environment, or default to local file
DB_NAME = os.getenv("DB_PATH", "corex.db")

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def get_player_rank(score):
    if score >= 2000:
        return "Warlord"
    elif score >= 1000:
        return "Veteran"
    elif score >= 500:
        return "Scout"
    else:
        return "Recruit"

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
            "achievements": all_achievements
        })
    
    conn.close()
    
    return render_template('index.html', data=dashboard_data)

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
