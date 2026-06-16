FROM python:3.11

WORKDIR /app

ENV TZ=Asia/Kuala_Lumpur

RUN apt-get update && apt-get install -y \
    tzdata \
    build-essential \
    cmake \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev

COPY requirements.txt .

RUN pip install --upgrade pip

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD gunicorn app:app --bind 0.0.0.0:$PORT