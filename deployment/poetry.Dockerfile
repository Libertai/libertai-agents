ARG PYTHON_VERSION=3.11
ARG ENTRYPOINT="fastapi run src/main.py"

FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi;

COPY . .

EXPOSE 8000

ENTRYPOINT ${ENTRYPOINT}
