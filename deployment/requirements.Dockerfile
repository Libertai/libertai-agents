ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim

ARG ENTRYPOINT="fastapi run src/main.py"

WORKDIR /app

COPY pyproject.toml ./

RUN pip install --no-cache-dir .;

COPY . .

EXPOSE 8000

ENTRYPOINT ${ENTRYPOINT}
