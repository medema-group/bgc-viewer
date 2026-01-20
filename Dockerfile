# Production/demo BGC Viewer instance
FROM python:3.11-slim

# Create application directory
WORKDIR /app

# Create data directories
RUN mkdir -p /data_root /index

# Copy demo JSON files to data_root and database to index
COPY demos/data/*.json /data_root/
COPY demos/data/attributes.db /index/

# Install the latest bgc-viewer from PyPI with Redis support
RUN pip install --no-cache-dir bgc-viewer[redis]

# # Copy and install local code instead of PyPI version
# COPY backend/ /app/backend/
# WORKDIR /app/backend
# RUN pip install --no-cache-dir -e ".[redis]"
# WORKDIR /app

# Set environment variables with defaults
ENV BGCV_PUBLIC_MODE=true \
    REDIS_URL=redis://redis:6379 \
    BGCV_HOST=0.0.0.0 \
    BGCV_PORT=5000 \
    PYTHONUNBUFFERED=1

# Expose the application port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/version').read()" || exit 1

# Run the application
CMD ["python", "-m", "bgc_viewer.app"]
