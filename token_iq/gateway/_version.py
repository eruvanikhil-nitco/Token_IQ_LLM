import importlib_metadata

try:
    version = importlib_metadata.version("token-iq")
except Exception:
    version = "unknown"
