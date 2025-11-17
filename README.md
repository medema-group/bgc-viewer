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

The projects consists of a number of modules, which are available in their respective folders as self-contained packages:

- **backend**: Python Flask server that serves the API and statically built frontend.
- **frontend**: Vue.js web application that, together with the API, makes a stand-alone viewer.
- **viewer-components**: Reusable TS/JS components for the frontend.

The backend is a comprehensive server that preprocesses, searches and dynamically loads data from a root directory containing huge amounts of data. The backend is not strictly necessary; the viewer can also run with other types of data sources. The backend serves from the local file system in local mode, or from a fixed data directory in public mode [see configuration](#configuration).

The BGC Viewer is a stand-alone application, but the frontend components can be used separately in other applications.

The frontend contains a built copy of the viewer-components. Similarly, the backend (Python package) contains a built copy of the frontend, so the resulting Python package will contain everything that is needed to run the application.


## Installation & usage

For end-users, see this README: [backend/README.md](backend/README.md). For development, a number of different scenarios is possible.

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- nodejs / npm

### Build, install & run all modules

To build all modules (viewer-components, frontend, backend), execute the build script from the repository root.

```bash
./build.sh
```

You can then install and run the built Python package as follows (replace {VERSION} with built version)

```bash
pip install backend/dist/bgc_viewer-{VERSION}-py3-none-any.whl
bgc-viewer
```

### Viewer-components development

```bash
cd viewer-components/

# Install
npm install

# Run dev server
npm run dev

# Build
npm run build
```

### Frontend development

TODO: some copying of assets from the viewer-components is required. See [./build.sh](./build.sh) script for now.

```bash
cd frontend/

# Install
npm install

# Run dev server
npm run dev

# Build
npm run build
```

### Backend (Python package) development

TODO: some copying of assets from the frontend is required. See [./build.sh](./build.sh) script for now.

```bash
cd backend/

# Setup environment and install
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# Set up configuration if required (see below)

# Run dev server
uv run python -m bgc_viewer.app

# Build
uv build
```

## Configuration

Environment variables can be set to change the configuration of the viewer.
A convenient way to change them is to put a file called `.env` in the directory from
which you are running the application.

```bash
# Server configuration
BGCV_HOST=localhost              # Server host (default: localhost)
BGCV_PORT=5005                   # Server port (default: 5005)
BGCV_DEBUG_MODE=False            # Enable dev/debug mode (default: False)
HTTPS_ENABLED=false              # Set to 'true' in production with HTTPS

# Public mode
# In public mode, there won't be an option to access the file system; the database path will be fixed.
# The DATABASE_PATH and DATA_ROOT below are the locations on the host that will be mounted to fixed
# paths inside the container, i.e. the values are used by docker-compose only.
BGCV_PUBLIC_MODE=True                       # Default is False (local mode), but set to True in Dockerfile.
BGCV_DATABASE_PATH=/path/to/attributes.db   # In public mode, path to the index database file on the host.
BGCV_DATA_ROOT=/path/to/data                # In public mode, path to the data root directory on the host.
BGCV_ALLOWED_ORIGINS=https://yourdomain.com # Allowed CORS origins, relevant for public mode.

# Session management
BGCV_SECRET_KEY=your-secret-key             # Required for production - secret key for session signing
REDIS_URL=redis://localhost:6379            # In public mode, this url will be used for session storage
SESSION_DIR=/tmp/sessions                   # Session directory for filesystem storage (fallback)
```

For more detailed configuration options, see [backend/.env.example](backend/.env.example).

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
