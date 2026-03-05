# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install system dependencies (needed for image processing and gallery-dl)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the bot code
COPY bot.py .

# Command to run the bot
CMD ["python", "bot.py"]
