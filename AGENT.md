# Project Agent Notes

Use a standard Python virtual environment when running, testing, or developing this
project. Do not use `uv` for environment management.

Recommended setup:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```
