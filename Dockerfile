# Use the highly stable 'bookworm' (Debian 12) so Playwright installs perfectly
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

# Install Playwright and its browser dependencies (The Plan D Upgrade)
RUN playwright install chromium --with-deps

# Copy the bot code
COPY bot.py .

# Command to run the bot (Shell form to prevent Render bracket errors)
CMD python bot.py
