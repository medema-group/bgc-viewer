#!/bin/bash

# Serve the combined documentation locally
PORT=${1:-8080}

if [ ! -d "_site" ]; then
  echo "Error: Built documentation not found in _site/"
  echo "Please run ./scripts/build-docs.sh first"
  exit 1
fi

echo "Serving documentation at http://localhost:$PORT"
echo "Press Ctrl+C to stop"
echo

# Use Python's built-in HTTP server
python3 -m http.server $PORT -d _site
