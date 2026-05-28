FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY src/ ./src/
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

VOLUME ["/data", "/secrets"]
EXPOSE 3000

CMD ["python", "src/main.py"]
