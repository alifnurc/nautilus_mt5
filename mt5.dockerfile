FROM ubuntu:25.04

WORKDIR /app

# Set environment variables for wine
ENV WINEARCH=win64
ENV WINEPREFIX=/app/mt5
ENV WINEDEBUG=-all,err-toolbar,fixme-all

# Install dependencies
RUN apt-get update && \
  apt-get install -y \
    wget \
    gpg \
    cabextract \
    x11vnc \
    xvfb \
    unzip \
    git && \
  dpkg --add-architecture i386 && \
  mkdir -pm755 /etc/apt/keyrings && \
  wget -O /tmp/winehq.key https://dl.winehq.org/wine-builds/winehq.key && \
  gpg --dearmor -o /etc/apt/keyrings/winehq-archive.key /tmp/winehq.key && \
  wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/plucky/winehq-plucky.sources && \
  apt-get update && \
  apt-get install --install-recommends -y winehq-staging && \
  rm /tmp/winehq.key && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install winetricks
RUN wget -O winetricks "https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks" && \
  chmod +x winetricks && \
  mv winetricks /usr/bin/

# Install novnc
RUN wget -O noVNC.zip https://github.com/novnc/noVNC/archive/refs/heads/master.zip && unzip noVNC.zip && rm noVNC.zip

# Set up python in wine environment
COPY requirements-wine.txt ./
