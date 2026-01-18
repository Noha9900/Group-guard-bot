# Use a lightweight Python base
FROM python:3.10-slim-buster

# Set working directory
WORKDIR /app

# Install system-level dependencies for streaming and mirroring
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    aria2 \
    rclone \
    git \
    curl \
    python3-dev \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python libraries
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the bot's code
COPY . .

# Environment Variables (Best practice: pass these at runtime)
ENV PYTHONUNBUFFERED=1

# Start the bot
CMD ["python3", "bot.py"]

