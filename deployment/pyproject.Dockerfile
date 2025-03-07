ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

RUN apt-get update && apt-get install build-essential -y && && apt-get clean

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt;

COPY . .

EXPOSE 8000
