FROM python:3.11-slim

WORKDIR /app

# Install PostgreSQL client and necessary system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    postgresql-client \
    curl \
    gnupg2 \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY pyproject.toml .
COPY uv.lock .

# Install Python dependencies
RUN pip install --no-cache-dir pip --upgrade && \
    pip install --no-cache-dir uv && \
    uv pip install --no-cache-dir -e .

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV USE_MOCK_TIGER=true

# Create streamlit config directory and write config
RUN mkdir -p /root/.streamlit
RUN echo "\
[server]\n\
headless = true\n\
port = 5000\n\
address = 0.0.0.0\n\
" > /root/.streamlit/config.toml

# Make entrypoint script executable
RUN chmod +x docker-entrypoint.sh

# Expose port
EXPOSE 5000

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

# Use the entrypoint script to wait for database and initialize it if needed
ENTRYPOINT ["./docker-entrypoint.sh"]