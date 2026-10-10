# Copyright (c) 2026 Yukihiko Shinoda
"""A configuration value read from a Docker secret file or an environment variable."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class Setting:
    """A configuration value, read from its Docker secret file when one exists, else from its environment variable.

    A secret file takes priority so a value mounted into a container never leaks through the process environment.
    """

    def __init__(self, environment_variable: str, secret_path: Path | None = None) -> None:
        self.environment_variable = environment_variable
        self.secret_path = secret_path

    def __repr__(self) -> str:
        # Names where the value comes from, never the value itself, which may be a credential.
        return f"Setting({self.environment_variable!r}, secret_path={self.secret_path!r})"

    def is_set(self) -> bool:
        """Return whether either the secret file or the environment variable is available."""
        return self._has_secret_file() or self.environment_variable in os.environ

    def read(self) -> str:
        """Return the value, raising KeyError when neither the secret file nor the environment variable is set."""
        if self.secret_path is not None and self._has_secret_file():
            return self.secret_path.read_text(encoding="utf-8").strip()
        return os.environ[self.environment_variable]

    def _has_secret_file(self) -> bool:
        return self.secret_path is not None and self.secret_path.exists()
