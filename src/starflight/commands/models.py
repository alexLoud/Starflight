"""Data types used by the application command registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Command:
    """describes an executable ui command."""

    id: str
    title: str
    menu_path: tuple[str, ...]
    shortcut: str | None = None
    toolbar_visible: bool = False
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("command id must not be empty")
        if not self.title.strip():
            raise ValueError("command title must not be empty")
        if not self.menu_path:
            raise ValueError("menu_path must not be empty")


class CommandHandler(Protocol):
    """signature for command handlers."""

    def __call__(self) -> None:
        """execute the command."""


__all__ = ["Command", "CommandHandler"]
