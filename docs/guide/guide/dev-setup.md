# Developer Setup

This guide covers setting up BGC Viewer for development.

## Prerequisites

- **Python** 3.11 or higher
- **Node.js** 18 or higher
- **Rust** (optional, for building Rust extensions)
- **Git**

## Clone the Repository

```bash
git clone https://github.com/medemagroup/bgc-viewer.git
cd bgc-viewer
```

## Backend Development Setup

### Install Backend Dependencies

Using `uv` (recommended):

```bash
cd backend
uv pip install -e ".[dev]"
```

Or using `pip`:

```bash
cd backend
pip install -e ".[dev]"
```

### Run Backend Server

```bash
cd backend
uv run python -m bgc_viewer.app
```

The API will be available at http://localhost:5000

## Frontend Development Setup

### Install Frontend Dependencies

```bash
cd frontend
npm install
```

### Run Development Server

```bash
cd frontend
npm run dev
```

The frontend will be available at http://localhost:5173

## Running Both Together

In separate terminal windows:

**Terminal 1 - Backend:**
```bash
cd backend
uv run python -m bgc_viewer.app
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

The application will be available at http://localhost:5173

## Build for Production

### Backend

The backend is installed as a package and automatically builds when you run `pip install -e .`

### Frontend

```bash
cd frontend
npm run build
```

This creates optimized production files in `frontend/build/`

## Running with Docker

For a quick development environment with both services:

```bash
docker-compose up
```

This will start both the backend API and frontend development server.

## Testing

### Backend Tests

```bash
cd backend
pytest
```

### Frontend Tests

```bash
cd frontend
npm test
```

## Troubleshooting

### Rust Extensions

If you encounter issues with Rust extensions, you can disable them:

```bash
export USE_RUST_EXTENSIONS=0
cd backend
pip install -e .
```

### Port Conflicts

If the default ports are in use, you can change them:

**Backend (port 8000):**
```bash
FLASK_RUN_PORT=8000 python -m bgc_viewer.app
```

**Frontend (port 3000):**
```bash
cd frontend
npm run dev -- --port 3000
```

## Next Steps

- [Developer Setup](./dev-setup.md) - Set up your development environment
- [Contributing Guide](../../CONTRIBUTING.md) - How to contribute to the project
- [REST API Reference](../api/overview.md) - API documentation
