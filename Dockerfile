FROM mcr.microsoft.com/playwright/python:v1.60.0-noble
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app

CMD ["xvfb-run", "-a", "python", "pipelines/daily_pipelines.py"]