"""OSMP MCP Server -- single source of truth for version."""

try:
    from importlib.metadata import version as _pkg_version, PackageNotFoundError
    try:
        __version__ = _pkg_version("osmp-mcp")
    except PackageNotFoundError:
        __version__ = "0.0.0+local"
except ImportError:
    __version__ = "0.0.0+local"
