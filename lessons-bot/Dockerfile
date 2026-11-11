FROM python:3.12-slim
WORKDIR /app
COPY *.py ./
ENV PYTHONUNBUFFERED=1 DB_PATH=/app/data/bot.db
VOLUME /app/data
CMD ["python", "main.py"]
