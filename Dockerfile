FROM python:3.11-slim
RUN apt-get update && apt-get install -y ffmpeg libsm6 libxext6 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# THIS LINE IS CRITICAL FOR PLAN D:
RUN playwright install chromium --with-deps 
COPY bot.py .
CMD ["python", "bot.py"]
