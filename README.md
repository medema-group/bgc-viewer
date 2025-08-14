# BGC-Viewer

| Badges | |
|:----:|----|
| **Build Status** | [![CI](https://github.com/medema-group/bgc-viewer/actions/workflows/ci.yml/badge.svg)](https://github.com/medema-group/bgc-viewer/actions/workflows/ci.yml) [![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) |
| **Software Directory** | [![Static Badge](https://img.shields.io/badge/RSD-BGCViewer-lib)](https://research-software-directory.org/software/bgc-viewer) |
| **License** | [![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0) |

A viewer for BGC data.


## Project Structure

```text
bgc-viewer/
├── bgc_viewer/             # Main application code
├── pyproject.toml          # Project configuration
└── README.md
```

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/medema-group/bgc-viewer.git
   cd bgc-viewer
   ```

2. Install with uv:

   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e ".[dev]"
   ```

## Usage

### Running the Server

```bash
uv run python -m bgc_viewer.app
```

The server will start on `http://localhost:5005` by default.

### API Endpoints

- `GET /` - Main HTML page
- `GET /api/data` - Get all custom data
- `GET /api/users` - Get user list
- `GET /api/users/<id>` - Get specific user
- `GET /api/stats` - Get application statistics
- `GET /api/health` - Health check endpoint

## Development

### Code Formatting

```bash
# Format code
uv run black bgc_viewer/

# Lint code
uv run flake8 bgc_viewer/

# Type checking
uv run mypy bgc_viewer/
```

### Testing

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=bgc_viewer
```

### Adding Custom Data

1. Create a `data/custom_data.json` file with your data structure
2. Modify the `load_custom_data()` function in `app.py` to read from your data source
3. Update the API endpoints to serve your custom data

## Customization

### Adding New Endpoints

1. Add new route functions to `app.py`
2. Update the HTML template to include new endpoints
3. Add corresponding JavaScript functions if needed

### Styling

Modify `static/css/style.css` to customize the appearance of the web interface.

### Frontend Behavior

Update `static/js/app.js` to add new interactive features.

## Environment Variables

Environment variables can be set to change the configuration of the viewer.
A convenient way to change them is to put a file called `.env` in the directory from
which you are running the application.

- `BGCV_HOST` - Server host (default: localhost)
- `BGCV_PORT` - Server port (default: 5005)
- `BGCV_DEBUG_MODE` - Enable dev/debug mode (default: False)

## License

Apache 2.0
