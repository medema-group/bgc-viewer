# BGC Viewer

| Badges | |
|:----:|----|
| **Build Status** | [![CI](https://github.com/medema-group/bgc-viewer/actions/workflows/ci.yml/badge.svg)](https://github.com/medema-group/bgc-viewer/actions/workflows/ci.yml) [![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) |
| **Software Directory** | [![Static Badge](https://img.shields.io/badge/RSD-BGCViewer-lib)](https://research-software-directory.org/software/bgc-viewer) |
| **License** | [![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0) |
| **Fairness** | [![fair-software.eu](https://img.shields.io/badge/fair--software.eu-%E2%97%8F%20%20%E2%97%8F%20%20%E2%97%8F%20%20%E2%97%8F%20%20%E2%97%8B-yellow)](https://fair-software.eu) |

A viewer for biosynthetic gene cluster data.

This is the development README. The README for end-users is here: [backend/README.md](backend/README.md) (it's the readme of the Python package)


## Project Structure

```text
bgc-viewer/
├── backend/             # Python Flask server that serves API and statically built frontend
├── frontend/            # Vue.js web application that, together with the API, makes a stand-alone viewer
├── viewer-components/   # Reusable TS/JS components for the frontend (WIP)
```

## Installation & usage

For end-users, see this README: [backend/README.md](backend/README.md). For development, follow the steps below.

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/medema-group/bgc-viewer.git
   cd bgc-viewer
   ```

2. Install backend with uv:

   ```bash
   cd backend/
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e ".[dev]"
   ```

## Configuration

Environment variables can be set to change the configuration of the viewer.
A convenient way to change them is to put a file called `.env` in the directory from
which you are running the application.

```bash
BGCV_HOST=localhost     # Server host (default: localhost)
BGCV_PORT=5005          # Server port (default: 5005)
BGCV_DEBUG_MODE=False   # Enable dev/debug mode (default: False)
```

### Running the Server

```bash
uv run python -m bgc_viewer.app
```

The server will start on `http://localhost:5005` by default.

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


## License

Apache 2.0
