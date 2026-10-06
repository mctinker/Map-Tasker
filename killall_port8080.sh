#!/usr/bin/env bash

# Kill all MapTasker instances: Get the unique PIDs listening on port 8080
pids=$(lsof -t -i :8080)

if [ -n "$pids" ]; then
    echo "Found PIDs on port 8080: $pids"
    # Kill the PIDs
    kill -9 $pids
    echo "Successfully sent SIGKILL to all processes."
else
    echo "No processes found running on port 8080."
fi