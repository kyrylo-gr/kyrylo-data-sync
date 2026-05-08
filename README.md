# kdata

`kdata` is a tiny Python client for storing and fetching JSON-compatible
dictionary data by key.

## Installation

Install directly from GitHub with `pip`:

```bash
pip install git+https://github.com/<owner>/<repo>.git
```

For local development, use Python's standard virtual environment tooling:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Usage

```python
from kdata import get, push

token = "secret-token"

push("example-key", {"status": "ok", "count": 3}, token)
data = get("example-key", token)
```

The default server URL is configured in `kdata/config.py`. Advanced callers and
tests can override it per call:

```python
push("example-key", {"status": "ok"}, token, url="https://mock.test")
data = get("example-key", token, url="https://mock.test")
```

## Value Rules

`push` accepts a Python dictionary, not a JSON string. The dictionary must be
JSON serializable, and its UTF-8 JSON-encoded size must be at most 1024 bytes.
