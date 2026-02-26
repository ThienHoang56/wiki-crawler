FROM python:3.13-slim

WORKDIR /app

# Cài Poetry
RUN pip install --no-cache-dir poetry

# Chỉ copy file dependency trước để tận dụng Docker layer cache
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --without dev

# Copy toàn bộ source
COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
