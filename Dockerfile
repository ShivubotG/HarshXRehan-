# Playwright + Chromium pre-installed official image
FROM mcr.microsoft.com/playwright/python:v1.47.0-noble

# Workdir
WORKDIR /app

# Copy dependency list and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Service will listen on this port
EXPOSE 5000

# Start Flask app
CMD ["python", "app.py"]
