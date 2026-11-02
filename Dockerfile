FROM python:3.11-slim
WORKDIR /opt/project
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY controller controller
COPY benchmark benchmark
CMD ["python", "-m", "app.app"]
