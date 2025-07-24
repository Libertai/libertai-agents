FROM python:3.12-slim

WORKDIR /app

RUN pip install poetry

COPY ./pyproject.toml ./poetry.lock ./

RUN poetry install

COPY . .

CMD ["poetry", "run", "fastapi", "run", "main.py", "--host", "0.0.0.0"]