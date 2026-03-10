FROM python:3.11-slim

# System dependencies: ffmpeg for audio processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libavcodec-extra \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir "setuptools<58" tzdata && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /app/redpanal

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
