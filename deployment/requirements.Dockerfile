ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

COPY pyproject.toml ./

RUN pip install --no-cache-dir .;

COPY . .

EXPOSE 8000
