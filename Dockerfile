FROM python:3.13-slim

WORKDIR /app

COPY requirements-mcp.txt .
RUN pip install --no-cache-dir -r requirements-mcp.txt

COPY src ./src
COPY data ./data

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

CMD ["python", "-m", "src.mcp.mcp_server"]
