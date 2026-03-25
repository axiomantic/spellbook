FROM python:3.14-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy project
COPY . .

# Install project with dev dependency group
RUN uv sync --group dev --no-editable

# Default command: run integration tests
CMD ["uv", "run", "pytest", "tests/docker/", "-v", "--tb=short"]
