FROM python:3.12

WORKDIR /app

RUN pip install poetry

COPY ./pyproject.toml ./poetry.lock ./

RUN poetry install

COPY . .

CMD ["poetry", "run", "fastapi", "run", "src/main.py", "--host", "0.0.0.0"]