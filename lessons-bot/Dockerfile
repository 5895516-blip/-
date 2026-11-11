FROM python:3.12-slim
WORKDIR /app
COPY *.py ./
COPY panel ./panel
ENV PYTHONUNBUFFERED=1 DB_PATH=/app/data/bot.db
VOLUME /app/data
EXPOSE 8080
CMD ["python", "main.py"]
