# Production/demo BGC Viewer instance
FROM python:3.11-slim

# Create application directory
WORKDIR /app

# Create data directory
RUN mkdir -p /data

# Install the latest bgc-viewer from PyPI with Redis support
RUN pip install --no-cache-dir bgc-viewer[redis]

# Set environment variables with defaults
ENV BGCV_PUBLIC_MODE=true \
    REDIS_URL=redis://redis:6379 \
    BGCV_HOST=0.0.0.0 \
    BGCV_PORT=5000

# Expose the application port
EXPOSE 5000

# Volume for data files
VOLUME ["/data"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/version').read()" || exit 1

# Run the application
CMD ["python", "-m", "bgc_viewer.app"]
