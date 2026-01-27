#!/bin/sh
set -e

# Start the Python backend in the background
echo "Starting Bay API backend..."
python run.py &
BACKEND_PID=$!

# Wait for backend to be ready
echo "Waiting for backend to start..."
for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:8156/health > /dev/null 2>&1; then
        echo "Backend is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Backend failed to start within 30 seconds"
        exit 1
    fi
    sleep 1
done

# Start Nginx in the foreground
echo "Starting Nginx..."
exec nginx -g "daemon off;"
