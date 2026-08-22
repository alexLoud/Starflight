"""Load Qt translations and keep the active language consistent."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from starflight.app.constants import DEFAULT_LANGUAGE, package_dir

_I18N_DIR = package_dir() / "i18n"
_ACTIVE_TRANSLATORS: list[QTranslator] = []


def tr_validation(message: str) -> str:
    """
    translate validation message.

    message
        English source validation message
    """

    translations = {
        "Please load an image first.": QCoreApplication.translate(
            "Validation", "Please load an image first."
        ),
        "The image was not found. Please load it again.": QCoreApplication.translate(
            "Validation", "The image was not found. Please load it again."
        ),
        "Target resolution must be at least 480 pixels.": QCoreApplication.translate(
            "Validation", "Target resolution must be at least 480 pixels."
        ),
        "Width and height must be even numbers.": QCoreApplication.translate(
            "Validation", "Width and height must be even numbers."
        ),
        "Video length must be between 3 and 60 seconds.": QCoreApplication.translate(
            "Validation", "Video length must be between 3 and 60 seconds."
        ),
        "Frame rate must be 24, 30, or 60 fps.": QCoreApplication.translate(
            "Validation", "Frame rate must be 24, 30, or 60 fps."
        ),
        "Star count must be between 50 and 3000.": QCoreApplication.translate(
            "Validation", "Star count must be between 50 and 3000."
        ),
        "The smallest star size must be below the largest.": QCoreApplication.translate(
            "Validation", "The smallest star size must be below the largest."
        ),
        "FFmpeg was not found. Install FFmpeg and make sure it is available on PATH.": (
            QCoreApplication.translate(
                "Validation",
                "FFmpeg was not found. Install FFmpeg and make sure it is available on PATH.",
            )
        ),
    }
    return translations.get(message, message)


def available_languages() -> dict[str, str]:
    """Return supported language codes and translated display names."""

    return {
        "de": QCoreApplication.translate("SettingsDialog", "German"),
        "en": QCoreApplication.translate("SettingsDialog", "English"),
    }


def normalize_language_code(code: str | None) -> str:
    """
    normalize a language code to a supported value.

    code
        requested language code
    """

    if not code:
        return DEFAULT_LANGUAGE
    normalized = code.strip().lower().replace("_", "-")
    if normalized.startswith("de"):
        return "de"
    if normalized.startswith("en"):
        return "en"
    return DEFAULT_LANGUAGE


def install_translators(app: QApplication, language_code: str) -> str:
    """
    install qt translators for the requested language.

    app
        running qapplication instance
    language_code
        language code such as de or en

    returns the active language code
    """

    global _ACTIVE_TRANSLATORS

    for translator in _ACTIVE_TRANSLATORS:
        app.removeTranslator(translator)
    _ACTIVE_TRANSLATORS.clear()

    active = normalize_language_code(language_code)
    if active != "en":
        qm_path = _I18N_DIR / f"starflight_{active}.qm"
        if qm_path.exists():
            translator = QTranslator(app)
            if translator.load(str(qm_path)):
                app.installTranslator(translator)
                _ACTIVE_TRANSLATORS.append(translator)

        qt_translator = QTranslator(app)
        translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        if qt_translator.load(QLocale(active), "qtbase", "_", translations_path):
            app.installTranslator(qt_translator)
            _ACTIVE_TRANSLATORS.append(qt_translator)

    QLocale.setDefault(QLocale(active))
    return active


def retranslate_ui(root: object | None) -> None:
    """
    retranslate ui after language change.

    root
        root widget with retranslate_ui method
    """

    if root is not None and hasattr(root, "retranslate_ui"):
        root.retranslate_ui()


__all__ = [
    "available_languages",
    "install_translators",
    "normalize_language_code",
    "retranslate_ui",
    "tr_validation",
]
