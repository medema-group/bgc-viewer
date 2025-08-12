# Contributing to BGC-Viewer

Thank you for your interest in contributing to BGC-Viewer! This document provides guidelines for contributing to the project.

## Getting Started

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Git

### Setting up the Development Environment

1. Fork the repository on GitHub
2. Clone your fork locally:

   ```bash
   git clone https://github.com/YOUR-USERNAME/bgc-viewer.git
   cd bgc-viewer
   ```

3. Create a virtual environment and install dependencies:

   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e ".[dev]"
   ```

4. Install pre-commit hooks (optional but recommended):

   ```bash
   pre-commit install
   ```

## Development Guidelines

### Code Style

We use several tools to maintain code quality:

- **Black**: Code formatter
- **Flake8**: Linting
- **MyPy**: Type checking

Run these tools before committing:

```bash
black .
flake8 .
mypy bgc_viewer/
```

### Testing

- Write tests for new functionality
- Ensure all tests pass before submitting a PR:

  ```bash
  pytest tests/
  ```

- Aim for good test coverage

### Commit Messages

Use clear, descriptive commit messages. Follow the format:

```text
type: brief description

Optional longer explanation of the change.
```

Types:

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

## Submitting Changes

1. Create a new branch for your feature/fix:

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and commit them
3. Push to your fork:

   ```bash
   git push origin feature/your-feature-name
   ```

4. Create a Pull Request on GitHub

### Pull Request Guidelines

- Provide a clear description of the changes
- Reference any related issues
- Ensure CI tests pass
- Request review from maintainers

## Code of Conduct

Please be respectful and constructive in all interactions. We aim to create a welcoming environment for all contributors.

## Questions?

If you have questions about contributing, please open an issue or reach out to the maintainers.

Thank you for contributing!
