#!/bin/bash
set -e

# Start Xvfb virtual display
RESOLUTIONS=("1920x1080" "1366x768" "1440x900" "1536x864" "1280x1024")
RESOLUTION=${RESOLUTIONS[$RANDOM % ${#RESOLUTIONS[@]}]}

Xvfb :99 -screen 0 ${RESOLUTION}x24 -ac -nolisten tcp -dpi 96 &
export DISPLAY=:99
sleep 2

echo "Virtual display OK — ${RESOLUTION}x24bit"
exec python run.py
