"""Allow `python -m vidmill ...` (used by the web UI to spawn real CLI runs)."""

from .cli import main

if __name__ == "__main__":
    main()
