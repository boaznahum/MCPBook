"""Version information read from resource file using importlib.resources."""

from importlib import resources


def get_version() -> str:
    """Read version string from resources/version.txt."""
    return (
        resources.files("web.resources")
        .joinpath("version.txt")
        .read_text()
        .strip()
    )


def get_connect_message() -> str:
    """Return the status bar connect message with version."""
    return f"connect v{get_version()}"
