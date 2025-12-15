#!/usr/bin/env bash

# Setup display
export DISPLAY=:100
Xvfb :100 -ac -screen 0 1024x768x24 &
x11vnc -display :100 -forever -rfbport 50319 -rfbauth /app/config/passwd &
chmod 600 /app/config/passwd
/app/noVNC-master/utils/novnc_proxy --vnc localhost:50319 --listen 60832 &

# Run MT5 terminal
wine C:/Program\ Files/MetaTrader\ 5/terminal64.exe /config:config/mt5cfg.ini &

# Run RPyC server
wine python -m pymt5linux --host mt5-wine --port 18847 C:/Program\ Files/Python313/python.exe &

while true
do
  sleep 1
done
