# Use a lightweight Python base image
FROM python:3.10-slim

# Install system dependencies
# FFmpeg is CRITICAL for streaming (pytgcalls) and downloading (yt-dlp)
RUN apt-get update && \
    apt-get install -y ffmpeg git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python libraries
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of your bot's code
COPY . .

# Command to start the bot
CMD ["python", "bot.py"]
