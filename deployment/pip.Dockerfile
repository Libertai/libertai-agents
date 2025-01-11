ARG PYTHON_VERSION=3.11
ARG ENTRYPOINT="fastapi run src/main.py"

FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt;

COPY . .

EXPOSE 8000

ENTRYPOINT ${ENTRYPOINT}
