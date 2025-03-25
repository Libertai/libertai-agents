ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

# RUN apt-get update && apt-get install build-essential -y && && apt-get clean

COPY pyproject.toml poetry.lock ./

RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi;

COPY . .

EXPOSE 8000
