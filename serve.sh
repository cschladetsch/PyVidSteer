#!/usr/bin/env zsh

PORT=8000

# kill anything already on the port
PIDS=$(lsof -ti tcp:${PORT})
if [[ -n "$PIDS" ]]; then
    echo "Killing existing process(es) on port ${PORT}: ${PIDS}"
    echo "$PIDS" | xargs kill -9
    sleep 0.5
fi

# activate venv if not already active
if [[ -z "$VIRTUAL_ENV" ]]; then
    source .venv/bin/activate
fi

python3 -m uvicorn interactivegen.server:app --reload --port ${PORT}
