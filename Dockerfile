# Use a lightweight Python base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Ensure entrypoint is executable
RUN chmod +x entrypoint.sh

# Expose the Web UI port
EXPOSE 5000

# The command to run when the container starts
ENTRYPOINT ["./entrypoint.sh"]
