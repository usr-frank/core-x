# Use a lightweight Python base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Initialize the database inside the container
RUN python3 init_db.py

# Expose the Web UI port
EXPOSE 5000

# The command to run when the container starts
# We run the scanner once, then start the web server
CMD python3 scanner.py && python3 app.py
