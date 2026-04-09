FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data

ENV GAPHUNTER_DB=/data/leaklab.db
ENV PORT=5000

EXPOSE 5000

CMD gunicorn api.app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
