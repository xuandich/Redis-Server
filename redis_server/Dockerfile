FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir redis rq docker

COPY config.py main.py orchestrator.py ./

CMD ["python", "orchestrator.py"]
