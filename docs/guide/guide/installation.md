# Installation

This guide covers installation for both the backend and frontend components of BGC Viewer.

## Prerequisites

- **Python** 3.8 or higher
- **Node.js** 18 or higher
- **Rust** (optional, for building extensions)

## Backend Installation

### Using pip

```bash
cd backend
pip install -e .
```

### Using uv (recommended)

```bash
cd backend
uv pip install -e .
```

### Development Installation

For development with all dependencies:

```bash
cd backend
pip install -e ".[dev]"
```

## Frontend Installation

### Install Dependencies

```bash
cd frontend
npm install
```

### Development Server

```bash
npm run dev
```

### Build for Production

```bash
npm run build
```

## Docker Installation

You can also run BGC Viewer using Docker:

```bash
docker-compose up
```

This will start both the backend API and frontend development server.

## Verify Installation

### Backend

```bash
cd backend
python -m bgc_viewer.app
```

Visit http://localhost:5000/api/health to verify the API is running.

### Frontend

```bash
cd frontend
npm run dev
```

Visit http://localhost:5173 to see the application.

## Troubleshooting

### Rust Extensions

If you encounter issues with Rust extensions, you can disable them:

```bash
export USE_RUST_EXTENSIONS=0
pip install -e .
```

### Port Conflicts

If the default ports are in use, you can change them:

**Backend:**
```bash
FLASK_RUN_PORT=8000 python -m bgc_viewer.app
```

**Frontend:**
```bash
npm run dev -- --port 3000
```

## Next Steps

- [Quick Start Guide](./quick-start.md)
- [Configuration Options](./configuration.md)
