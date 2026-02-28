# Use official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Set working directory
WORKDIR /app

# Install system dependencies
# libgl1 and libglib2.0-0 are for OpenCV/Computer Vision
# curl is for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser and its dependencies
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy the rest of the application
COPY . .

# Create a non-root user and switch to it for security
# Ensure the user has access to playwright browsers
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Expose the port (API usually on 8000)
EXPOSE 8000

# Default command for the API (can be overridden in docker-compose for the worker)
CMD exec gunicorn --bind :$PORT --workers 1 --worker-class uvicorn.workers.UvicornWorker --timeout 0 app.api.main:app
