from flask import Flask, render_template_string
import sqlite3
import os  # <--- This was missing!

app = Flask(__name__)
# Get DB path from Docker environment, or default to local file
DB_NAME = os.getenv("DB_PATH", "corex.db")

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    
    # JOIN with players table to get the real name
    query = '''
        SELECT 
            p.gamertag, 
            p.uuid,
            COUNT(u.achievement_id) as score,
            (SELECT COUNT(*) FROM definitions) as total_possible
        FROM players p
        LEFT JOIN unlocks u ON p.uuid = u.player_uuid
        GROUP BY p.uuid
        ORDER BY score DESC
    '''
    players = conn.execute(query).fetchall()
    
    dashboard_data = []
    for p in players:
        unlocks = conn.execute('''
            SELECT d.name, d.description, d.icon, u.unlocked_at 
            FROM unlocks u
            JOIN definitions d ON u.achievement_id = d.id
            WHERE u.player_uuid = ?
            ORDER BY u.unlocked_at DESC
        ''', (p['uuid'],)).fetchall()
        
        dashboard_data.append({
            "name": p['gamertag'] if p['gamertag'] else p['uuid'][:8],
            "score": p['score'] * 100,
            "unlocks": unlocks
        })
    
    conn.close()
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>CORE-X | Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { background-color: #0f0f12; color: #e0e0e0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; }
            .container { max_width: 800px; margin: 0 auto; }
            h1 { letter-spacing: 4px; border-bottom: 2px solid #00ce7c; padding-bottom: 15px; color: #fff; text-transform: uppercase; font-size: 1.5rem; }
            .player-card { background: #18181b; padding: 20px; margin-bottom: 20px; border-radius: 12px; border: 1px solid #27272a; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
            .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
            .gamertag { font-size: 1.5em; font-weight: bold; color: #fff; }
            .gs { color: #00ce7c; font-weight: bold; background: rgba(0, 206, 124, 0.1); padding: 5px 10px; border-radius: 4px; }
            .achievement { display: flex; align-items: center; padding: 12px 0; border-top: 1px solid #27272a; }
            .icon { font-size: 2.5em; margin-right: 20px; width: 50px; text-align: center; }
            .title { font-weight: bold; color: #ddd; display: block; }
            .desc { font-size: 0.9em; color: #888; }
            .date { font-size: 0.75em; color: #555; display: block; margin-top: 4px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Core-X // Vanguard</h1>
            {% for player in data %}
            <div class="player-card">
                <div class="header">
                    <div class="gamertag">{{ player.name }}</div>
                    <div class="gs">{{ player.score }} G</div>
                </div>
                {% for ach in player.unlocks %}
                <div class="achievement">
                    <div class="icon">{{ ach.icon }}</div>
                    <div>
                        <span class="title">{{ ach.name }}</span>
                        <span class="desc">{{ ach.description }}</span>
                        <span class="date">{{ ach.unlocked_at }}</span>
                    </div>
                </div>
                {% endfor %}
            </div>
            {% endfor %}
            
            {% if not data %}
            <p>System Online. Waiting for player data...</p>
            {% endif %}
        </div>
    </body>
    </html>
    """
    return render_template_string(html, data=dashboard_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
