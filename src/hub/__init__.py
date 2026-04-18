from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("hub-cli")
except PackageNotFoundError:
    __version__ = "unknown"
