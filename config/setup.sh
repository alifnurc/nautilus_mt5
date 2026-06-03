#!/usr/bin/env bash

# Setup display
export DISPLAY=:100
Xvfb :100 -ac -screen 0 1024x768x24 &
x11vnc -display :100 -forever -rfbport 50319 -rfbauth /app/config/passwd &
chmod 600 /app/config/passwd
/app/noVNC-master/utils/novnc_proxy --vnc localhost:50319 --listen 60832 &

# Install MT5
if [ ! -f "$WINEPREFIX/drive_c/Program Files/MetaTrader 5/terminal64.exe" ]; then
  wget "https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe" && \
  wine mt5setup.exe /auto
fi

# Install Python
if [ ! -d "$WINEPREFIX/drive_c/Program Files/Python313"]; then
  wget -O python-installer.exe "https://www.python.org/ftp/python/3.13.9/python-3.13.9-amd64.exe"
  wine python-installer.exe InstallAllUsers=1 PrependPath=1 /quiet
  wine pip install -r requirements-wine.txt
fi

# Run MT5 terminal
wine C:/Program\ Files/MetaTrader\ 5/terminal64.exe /config:/app/config/mt5cfg.ini &

# Run RPyC server
wine python -m pymt5linux --host mt5-wine --port 18847 C:/Program\ Files/Python313/python.exe &

while true
do
  sleep 1
done
