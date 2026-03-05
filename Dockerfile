# CRITICAL FIX: Use 'bookworm' (Debian 12) instead of 'slim' (Debian 13)
# This ensures Playwright's dependency installer finds the exact package names it wants.
FROM python:3.11-bookworm

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

# Install Playwright and its browser dependencies
RUN playwright install chromium --with-deps

# Copy the bot code
COPY bot.py .

# Command to run the bot
CMD ["python", "bot.py"]]
