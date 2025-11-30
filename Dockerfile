FROM python:3.10-slim

# Install system dependencies including Chromium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    apt-transport-https \
    fonts-indic \
    fonts-noto \
    fonts-freefont-ttf \
    libnss3 \
    libxss1 \
    libasound2 \
    libxtst6 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and browsers
RUN playwright install chromium
RUN playwright install-deps

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /tmp/playwright

# Expose port
EXPOSE 10000

# Start application
CMD ["python", "app.py"]
