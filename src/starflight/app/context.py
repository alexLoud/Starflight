"""Create the services shared by controllers and views."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import QSettings

from starflight.app.logging import configure_logging
from starflight.app.settings import create_settings
from starflight.commands.registry import CommandRegistry
from starflight.services.error_service import ErrorService


@dataclass(slots=True)
class AppContext:
    """central runtime objects for the application."""

    logger: logging.Logger
    error_service: ErrorService
    settings: QSettings
    command_registry: CommandRegistry


def create_app_context() -> AppContext:
    """create application context without ui dependencies."""

    logger = configure_logging()
    error_service = ErrorService(logger)
    settings = create_settings()
    command_registry = CommandRegistry(error_service)

    return AppContext(
        logger=logger,
        error_service=error_service,
        settings=settings,
        command_registry=command_registry,
    )


__all__ = ["AppContext", "create_app_context"]
