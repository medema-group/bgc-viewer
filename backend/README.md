# BGC Viewer

A viewer for biosynthetic gene cluster (BGC) data.


## Installation & run

Using Python 3.11 or higher, install and run the BGC Viewer as follows:

```bash
pip install bgc-viewer
bgc-viewer
```

This will start the BGC Viewer server, to which you can connect with your web browser.


## Configuration

Environment variables can be set to change the configuration of the viewer.
A convenient way to change them is to put a file called `.env` in the directory from
which you are running the application.

### Basic Configuration

```bash
BGCV_HOST=localhost       # Server host (default: localhost)
BGCV_PORT=5005            # Server port (default: 5005)
BGCV_DEBUG_MODE=false     # Enable dev/debug mode (default: false)
```

### Public Mode (Multi-user Deployment)

```bash
BGCV_PUBLIC_MODE=true                       # Enable public mode
BGCV_INDEX_FILENAME=attributes.db           # Index database filename (default: attributes.db)
BGCV_SECRET_KEY=your-secret-key             # Secret key for session signing (required)
REDIS_URL=redis://localhost:6379            # Redis URL for session storage (recommended)
HTTPS_ENABLED=true                          # Enable secure cookies for HTTPS
BGCV_ALLOWED_ORIGINS=https://yourdomain.com # Allowed CORS origins
```

In public mode:
- The index database file is expected at `/index/` (mounted volume in Docker)
- The data files are expected at `/data_root/` (mounted volume in Docker)
- Multiple users can access the application simultaneously with session support
- File system browsing and preprocessing endpoints are disabled

For more configuration options, see [.env.example](.env.example).

## Development

See the repository [main README](../README.md#backend-python-package-development) for development details.

```bash
uv run python -m bgc_viewer.app
```

## License

Apache 2.0
