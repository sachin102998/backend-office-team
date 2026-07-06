FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends wget gnupg fonts-liberation libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN pip install --no-cache-dir openai fastapi uvicorn apscheduler python-dotenv pydantic httpx reportlab python-docx openpyxl ddgs playwright
RUN python -m playwright install chromium
COPY . /tmp/src/
RUN mkdir -p /app/app/web && cp /tmp/src/*.py /app/app/ && cp /tmp/src/index.html /app/app/web/ && rm -rf /tmp/src
EXPOSE 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
