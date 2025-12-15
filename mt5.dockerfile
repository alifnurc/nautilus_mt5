FROM ubuntu:24.04

WORKDIR /app

# Set environment variables for wine
ENV WINEARCH=win64
ENV WINEPREFIX=/root/.mt5
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
    git

# Add repository
RUN dpkg --add-architecture i386 && \
  mkdir -pm755 /etc/apt/keyrings && \
  wget -O /tmp/winehq.key https://dl.winehq.org/wine-builds/winehq.key && \
  gpg --dearmor -o /etc/apt/keyrings/winehq-archive.key /tmp/winehq.key && \
  wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources

# Install wine
RUN apt-get update && \
  apt-get install --install-recommends -y winehq-stable

# Install winetricks
RUN wget -O winetricks "https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks" && \
  chmod +x winetricks && \
  mv winetricks /usr/bin/

# Install novnc
RUN wget -O noVNC.zip https://github.com/novnc/noVNC/archive/refs/heads/master.zip && unzip noVNC.zip && rm noVNC.zip

# Setup wine
RUN winecfg -v=win11 && \
  xvfb-run sh -c "winetricks --unattended vcrun2019"

# Set up python in wine environment
COPY requirements-wine.txt ./
RUN wget -O python-installer.exe "https://www.python.org/ftp/python/3.13.9/python-3.13.9-amd64.exe" && \
  xvfb-run wine python-installer.exe InstallAllUsers=1 PrependPath=1 /quiet && \
  wine pip install -r requirements-wine.txt

# Install MT5
RUN wget -O mt5-setup.exe "https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe" && \
   xvfb-run wine mt5-setup.exe /auto || true

# Clean up
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* requirements-wine.txt python-installer.exe mt5-setup.exe

# Start mt5-wine server
COPY config config
CMD ["config/setup.sh"]
