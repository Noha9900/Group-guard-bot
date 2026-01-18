# We MUST use Python 3.10 because py-tgcalls v1.x doesn't work on 3.12/3.13
FROM python:3.10-slim-buster

# Set the working directory
WORKDIR /app

# Install FFmpeg (Required for streaming & yt-dlp) and git
RUN apt-get update && \
    apt-get install -y ffmpeg git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the bot files
COPY . .

# Grant execution permissions to the start script
RUN chmod +x start.sh

# Start the bot
CMD ["bash", "start.sh"]
