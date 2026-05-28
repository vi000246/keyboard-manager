FROM python:3.12-slim

WORKDIR /app

# Install deps separately so source changes don't bust the layer cache.
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.32" \
    "pydantic>=2.9" \
    "websockets>=13"

# Copy backend source as a Python package — preserves `from .api.layout import ...`
# style relative imports used in main.py.
COPY . ./backend

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
