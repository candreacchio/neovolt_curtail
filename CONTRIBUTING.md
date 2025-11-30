# Contributing to Bytewatt Export Limiter

Thank you for your interest in contributing to the Bytewatt Export Limiter Home Assistant integration!

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Home Assistant development environment (optional, for full integration testing)

### Setting Up Your Development Environment

1. Clone the repository:
   ```bash
   git clone https://github.com/carlo/bytewatt-export-limiter.git
   cd bytewatt-export-limiter
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

4. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

## Code Quality

This project uses several tools to maintain code quality:

- **Ruff**: Linting and formatting
- **Mypy**: Static type checking
- **Pytest**: Testing

### Running Checks Locally

```bash
# Run linting
ruff check .

# Run formatting check
ruff format --check .

# Run type checking
mypy custom_components/bytewatt_export_limiter

# Run tests
pytest

# Run tests with coverage
pytest --cov=custom_components/bytewatt_export_limiter --cov-report=term-missing
```

### Pre-commit Hooks

Pre-commit hooks will run automatically before each commit. To run them manually:

```bash
pre-commit run --all-files
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_modbus_client.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov
```

### Writing Tests

- Place tests in the `tests/` directory
- Follow the naming convention `test_*.py`
- Use pytest fixtures from `conftest.py` for common setup
- Mock external dependencies (Modbus, Home Assistant core)

## Pull Request Process

1. Fork the repository and create your feature branch from `master`
2. Make your changes and ensure all tests pass
3. Update documentation if needed
4. Ensure your code follows the project's style guidelines (run pre-commit hooks)
5. Submit a pull request with a clear description of your changes

### Commit Messages

- Use clear, descriptive commit messages
- Reference any related issues (e.g., "Fixes #123")

## Code Style

- Follow PEP 8 guidelines (enforced by Ruff)
- Use type hints for all function signatures
- Add docstrings to classes and public methods
- Keep functions focused and reasonably sized

## Reporting Issues

When reporting issues, please include:

- Home Assistant version
- Integration version
- Steps to reproduce
- Expected vs actual behavior
- Relevant log entries (set logger level to debug for `custom_components.bytewatt_export_limiter`)

## Questions?

Feel free to open an issue for questions or discussions about the project.
