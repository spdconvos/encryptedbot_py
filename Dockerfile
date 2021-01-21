FROM python:3.8-slim

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app 

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . /app

CMD ["python", "Bot.py"]

