FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py curl_parser.py ./
COPY templates ./templates

ENV PYTHONUNBUFFERED=1
EXPOSE 7700
CMD ["python", "app.py"]
