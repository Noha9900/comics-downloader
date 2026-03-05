# Use an official Python runtime
FROM python:3.11-slim

# Install basic system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# CRITICAL UPGRADE: Install Playwright and all required browser dependencies
RUN playwright install chromium --with-deps

# Copy the bot code
COPY bot.py .

# Command to run the bot
CMD ["python", "bot.py"]
