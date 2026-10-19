FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY alertbot ./alertbot
ENV STATE_FILE=/data/alertbot-state.json
VOLUME ["/data"]
CMD ["python", "-m", "alertbot", "run"]
