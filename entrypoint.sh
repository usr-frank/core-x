#!/bin/bash
set -e

# Initialize Database
echo "🛠️  Initializing Database..."
python init_db.py

# Start Scanner in Background
echo "📡 Starting Background Scanner..."
python scanner.py &

# Start Web Server
echo "🚀 Starting Gunicorn Web Server..."
exec gunicorn --workers 3 --threads 2 --bind 0.0.0.0:5000 --access-logfile - --error-logfile - app:app
