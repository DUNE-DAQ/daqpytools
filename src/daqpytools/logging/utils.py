import os


def get_width() -> int:
    """Get the width of the terminal."""
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 300
