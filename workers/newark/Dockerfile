FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    wget curl \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libatspi2.0-0 libgtk-3-0 \
    libx11-6 libxcb1 libxext6 fonts-liberation xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Snap Chromium sẽ được mount vào /snap/chromium/current từ host
ENV CHROMIUM_PATH=/snap/chromium/current/usr/lib/chromium-browser/chrome
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

WORKDIR /app

COPY sourceCode/requirements.txt /tmp/src_requirements.txt
RUN pip install --no-cache-dir -r /tmp/src_requirements.txt

COPY sourceCode/ /app/sourceCode/
COPY run.py .

CMD ["python", "run.py"]
