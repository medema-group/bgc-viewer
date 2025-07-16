# BGC-Viewer

!!Work-in-progress!!

A viewer for BGC data.


## Project Structure

```
bgc-viewer/
├── bgc_viewer/
│   ├── __init__.py
│   ├── app.py              # Main Flask application
│   ├── static/
│   │   └── style.css       # Styling
│   │   └── app.js          # Frontend JavaScript
│   └── templates/
│       └── index.html      # Main HTML template
├── data/
│   └── custom_data.json    # Optional custom data file
├── tests/
│   └── test_app.py         # Test files
├── pyproject.toml          # Project configuration
├── README.md
└── .gitignore
```

## Setup

### Prerequisites

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

1. Clone or create the project directory:
   ```bash
   mkdir bgc-viewer
   cd bgc-viewer
   ```

2. Create the project structure and files (as shown above)

3. Initialize the project with uv:
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e .
   ```

4. For development dependencies:
   ```bash
   uv pip install -e ".[dev]"
   ```

## Usage

### Running the Server

```bash
# Using the console script
serve

# Or directly with Python
python -m bgc_viewer.app

# Or with environment variables
FLASK_DEBUG=true PORT=8000 serve
```

The server will start on `http://localhost:5005` by default.

### API Endpoints

- `GET /` - Main HTML page with interactive API tester
- `GET /api/data` - Get all custom data
- `GET /api/users` - Get user list
- `GET /api/users/<id>` - Get specific user
- `GET /api/stats` - Get application statistics
- `GET /api/health` - Health check endpoint

### Testing the API

Visit `http://localhost:5005` in your browser to access the interactive API tester, or use curl:

```bash
# Get all data
curl http://localhost:5005/api/data

# Get users
curl http://localhost:5005/api/users

# Get specific user
curl http://localhost:5005/api/users/1

# Health check
curl http://localhost:5005/api/health
```

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
