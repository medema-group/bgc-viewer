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
BGCV_DEBUG_MODE=False     # Enable dev/debug mode (default: False)
```

### Public Mode (Multi-user Deployment)

```bash
BGCV_PUBLIC_MODE=True                         # Enable public mode
BGCV_DATABASE_PATH=/path/to/attributes.db     # Path to index database file (required)
BGCV_SECRET_KEY=your-secret-key               # Secret key for session signing (required)
REDIS_URL=redis://localhost:6379              # Redis URL for session storage (recommended)
HTTPS_ENABLED=True                            # Enable secure cookies for HTTPS
BGCV_ALLOWED_ORIGINS=https://yourdomain.com   # Allowed CORS origins
```

In public mode:
- The database path points to an `attributes.db` index file
- The actual data location (data_root) is read from the database metadata
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
