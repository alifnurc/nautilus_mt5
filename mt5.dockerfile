FROM ubuntu:22.04

# Set environment variables for wine
ENV WINEARCH=win64
ENV WINEPREFIX=/root/.wine
ENV WINEDEBUG=-all,err-toolbar,fixme-all

# Install dependencies
RUN apt-get update && \
  apt-get install -y \
    wget \
    gpg \
    cabextract \
    xvfb

# Add repository
RUN dpkg --add-architecture i386 && \
  mkdir -pm755 /etc/apt/keyrings && \
  wget -O /tmp/winehq.key https://dl.winehq.org/wine-builds/winehq.key && \
  gpg --dearmor -o /etc/apt/keyrings/winehq-archive.key /tmp/winehq.key && \
  wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/jammy/winehq-jammy.sources

# Install wine
RUN apt-get update && \
  apt-get install --install-recommends -y winehq-stable

# Install winetricks
RUN wget -O winetricks "https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks" && \
  chmod +x winetricks && \
  mv winetricks /usr/bin/

# Setup wine
RUN wineboot -u && \
  xvfb-run sh -c "winetricks --unattended vcrun2019 ucrtbase2019 corefonts"

# Install Mono
RUN wget -O mono.msi "https://dl.winehq.org/wine/wine-mono/8.0.0/wine-mono-8.0.0-x86.msi" && \
  WINEDLLOVERRIDES=mscoree=d wine msiexec /i mono.msi /qn

# Install Gecko
RUN wget -O gecko64.msi "https://dl.winehq.org/wine/wine-gecko/2.47.4/wine-gecko-2.47.4-x86_64.msi" && \
  wine msiexec /i gecko64.msi /qn
RUN wget -O gecko86.msi "https://dl.winehq.org/wine/wine-gecko/2.47.4/wine-gecko-2.47.4-x86.msi" && \
  wine msiexec /i gecko86.msi /qn

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
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* requirements-wine.txt mono.msi gecko64.msi gecko86.msi python-installer.exe mt5-setup.exe

# Run RPyC server
RUN wine python -m pymt5linux --host localhost --port 18847 C:/Program\ Files/Python313/python.exe &

# Test connection
COPY tests/* ./
RUN xvfb-run -a wine python test_metatrader5.py 2>&1 | tee /tmp/test_metatrader5.log || cat /tmp/test_metatrader5.log
RUN xvfb-run -a python test_pymt5linux.py 2>&1 | tee /tmp/test_pymt5linux.log || cat /tmp/test_pymt5linux.log

# Start mt5-wine server
COPY config/setup.sh ./
CMD ["./setup.sh"]
