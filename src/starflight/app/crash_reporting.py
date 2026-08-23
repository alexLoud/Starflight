"""Persist diagnostic reports and native Python fault traces."""

from __future__ import annotations

import datetime as dt
import faulthandler
import importlib.metadata
import logging
import os
import platform
import sys
import tempfile
import threading
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import IO

from starflight.app.constants import APP_ID
from starflight.app.logging import get_log_file_path
from starflight.app.metadata import app_version

_REPORT_LIMIT = 10
_LOG_TAIL_LINES = 200


def _modified_time_ns(path: Path) -> int:
    """return a stable fallback value when a report timestamp cannot be read."""

    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


@dataclass(frozen=True, slots=True)
class CrashReport:
    """a persisted crash report ready for display or copying."""

    report_id: str
    text: str
    path: Path


class CrashReporter:
    """capture Python exceptions and native fault traces without depending on Qt."""

    def __init__(
        self,
        logger: logging.Logger,
        *,
        log_path: Path | None = None,
        report_directory: Path | None = None,
    ) -> None:
        self._logger = logger
        self.log_path = log_path or get_log_file_path()
        self.report_directory = report_directory or self.log_path.parent / "Crash Reports"
        self.native_fault_directory = self.report_directory / "Native Faults"
        self._fault_file: IO[str] | None = None
        self._fault_path: Path | None = None
        self._lock = threading.RLock()

    @property
    def logger(self) -> logging.Logger:
        """return the application logger used by this reporter."""

        return self._logger

    def start_native_fault_capture(self) -> None:
        """convert prior native traces into reports and arm capture for this process."""

        with self._lock:
            self._ensure_directories()
            self._collect_prior_native_faults()
            self._logger.info(
                "diagnostics initialized | app_version=%s | os=%s | python=%s",
                _safe_app_version(),
                platform.platform(),
                platform.python_version(),
            )
            self._fault_path = self.native_fault_directory / f"native-fault-{os.getpid()}.log"
            try:
                self._fault_file = self._fault_path.open("w", encoding="utf-8")
                faulthandler.enable(file=self._fault_file, all_threads=True)
            except (OSError, RuntimeError):
                self._logger.exception("native fault capture could not be enabled")
                if self._fault_file is not None:
                    self._fault_file.close()
                self._fault_file = None
                self._fault_path = None

    def shutdown(self) -> None:
        """disarm native capture and remove the empty current-session trace."""

        with self._lock:
            if self._fault_file is not None:
                try:
                    if faulthandler.is_enabled():
                        faulthandler.disable()
                except (OSError, RuntimeError):
                    self._logger.exception("native fault capture could not be disabled")
                finally:
                    try:
                        self._fault_file.close()
                    except OSError:
                        self._logger.exception("native fault trace could not be closed")
                    self._fault_file = None
            if self._fault_path is not None:
                try:
                    self._fault_path.unlink(missing_ok=True)
                except OSError:
                    self._logger.exception("native fault trace could not be removed")
                self._fault_path = None

    def capture_exception(
        self,
        context: str,
        exc: BaseException,
        tb: TracebackType | None = None,
    ) -> CrashReport:
        """log and persist an exception with its complete traceback."""

        traceback_object = tb if tb is not None else exc.__traceback__
        exception_info = (type(exc), exc, traceback_object)
        self._logger.error(context, exc_info=exception_info)
        trace_text = "".join(traceback.format_exception(*exception_info))
        try:
            return self._write_report(
                context=context,
                failure_type=f"{type(exc).__module__}.{type(exc).__qualname__}",
                failure_message=str(exc),
                diagnostic_details=trace_text,
            )
        except Exception as report_error:
            self._logger.error(
                "crash report generation failed",
                exc_info=(type(report_error), report_error, report_error.__traceback__),
            )
            report_id = uuid.uuid4().hex[:12]
            text = (
                "Starflight Crash Report\n"
                "=======================\n\n"
                f"Report ID: {report_id}\n"
                f"Context: {context}\n"
                f"Type: {type(exc).__module__}.{type(exc).__qualname__}\n"
                f"Message: {exc}\n\n"
                f"{trace_text}"
            )
            return CrashReport(
                report_id=report_id,
                text=text,
                path=self.report_directory / f"starflight-crash-{report_id}.pending.txt",
            )

    def pending_reports(self) -> list[CrashReport]:
        """return reports that have not yet been presented to the user."""

        with self._lock:
            self._ensure_directories()
            reports: list[CrashReport] = []
            for path in self._pending_report_paths():
                report = self._read_pending_report(path)
                if report is not None:
                    reports.append(report)
            return reports

    def latest_pending_report(self) -> tuple[CrashReport | None, list[Path]]:
        """return only the newest readable report plus every pending report path."""

        with self._lock:
            self._ensure_directories()
            paths = self._pending_report_paths()
            for path in reversed(paths):
                report = self._read_pending_report(path)
                if report is not None:
                    return report, paths
            return None, paths

    def mark_pending_reports_presented(self, paths: list[Path]) -> None:
        """acknowledge a pending-report backlog with a single retention pass."""

        with self._lock:
            for path in paths:
                self._mark_path_presented(path)
            self._prune_acknowledged_reports()

    def mark_presented(self, report: CrashReport) -> CrashReport:
        """mark a displayed report as acknowledged while retaining it on disk."""

        with self._lock:
            path = self._mark_path_presented(report.path)
            self._prune_acknowledged_reports()
            return CrashReport(report.report_id, report.text, path)

    def _pending_report_paths(self) -> list[Path]:
        return sorted(
            self.report_directory.glob("*.pending.txt"),
            key=lambda path: (_modified_time_ns(path), path.name),
        )

    def _read_pending_report(self, path: Path) -> CrashReport | None:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            self._logger.exception("pending crash report could not be read")
            return None
        report_id = path.name.removesuffix(".pending.txt").rsplit("-", 1)[-1]
        return CrashReport(report_id=report_id, text=text, path=path)

    def _mark_path_presented(self, path: Path) -> Path:
        if not path.name.endswith(".pending.txt"):
            return path
        acknowledged_path = path.with_name(f"{path.name.removesuffix('.pending.txt')}.txt")
        try:
            path.replace(acknowledged_path)
            return acknowledged_path
        except OSError:
            self._logger.exception("crash report could not be marked as presented")
            return path

    def _collect_prior_native_faults(self) -> None:
        for path in sorted(self.native_fault_directory.glob("native-fault-*.log")):
            try:
                details = path.read_text(encoding="utf-8", errors="replace").strip()
                if details:
                    fault_timestamp = dt.datetime.fromtimestamp(
                        path.stat().st_mtime,
                    ).astimezone()
                    self._logger.critical("native fault detected from previous session")
                    report = self._write_report(
                        context="native fault in previous application session",
                        failure_type="NativeProcessFault",
                        failure_message="The previous process terminated after a native fault.",
                        diagnostic_details=details,
                        timestamp=fault_timestamp,
                    )
                    if report.path.is_file():
                        path.unlink(missing_ok=True)
                    continue

                path.unlink(missing_ok=True)
            except OSError:
                self._logger.exception("prior native fault trace could not be processed")

    def _write_report(
        self,
        *,
        context: str,
        failure_type: str,
        failure_message: str,
        diagnostic_details: str,
        timestamp: dt.datetime | None = None,
    ) -> CrashReport:
        with self._lock:
            self._ensure_directories()
            report_timestamp = timestamp or dt.datetime.now().astimezone()
            report_id = uuid.uuid4().hex[:12]
            filename_timestamp = report_timestamp.astimezone(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
            path = self.report_directory / (
                f"starflight-crash-{filename_timestamp}-{report_id}.pending.txt"
            )
            text = self._format_report(
                report_id=report_id,
                timestamp=report_timestamp,
                context=context,
                failure_type=failure_type,
                failure_message=failure_message,
                diagnostic_details=diagnostic_details,
            )
            try:
                path.write_text(text, encoding="utf-8")
            except OSError:
                fallback = Path(tempfile.gettempdir()) / path.name
                try:
                    fallback.write_text(text, encoding="utf-8")
                    path = fallback
                except OSError:
                    self._logger.exception("crash report could not be persisted")
            return CrashReport(report_id=report_id, text=text, path=path)

    def _format_report(
        self,
        *,
        report_id: str,
        timestamp: dt.datetime,
        context: str,
        failure_type: str,
        failure_message: str,
        diagnostic_details: str,
    ) -> str:
        qt_version, pyside_version = _qt_versions()
        thread = threading.current_thread()
        lines = [
            "Starflight Crash Report",
            "=======================",
            "",
            f"Report ID: {report_id}",
            f"Timestamp: {timestamp.isoformat(timespec='milliseconds')}",
            f"Crash report directory: {self.report_directory}",
            f"Application log: {self.log_path}",
            f"Starflight version: {_safe_app_version()}",
            f"Operating system: {platform.platform()}",
            f"System: {platform.system()}",
            f"OS release: {platform.release()}",
            f"OS version: {platform.version()}",
            f"Architecture: {platform.machine()}",
            f"Python version: {platform.python_version()}",
            f"Python implementation: {platform.python_implementation()}",
            f"PySide version: {pyside_version}",
            f"Qt version: {qt_version}",
            f"Frozen application: {bool(getattr(sys, 'frozen', False))}",
            f"Executable: {sys.executable}",
            f"Process ID: {os.getpid()}",
            f"Thread: {thread.name} ({thread.ident})",
            "",
            "Failure",
            "-------",
            f"Context: {context}",
            f"Type: {failure_type}",
            f"Message: {failure_message or '<no message>'}",
            "",
            "Traceback / native fault details",
            "--------------------------------",
            diagnostic_details.rstrip() or "<no traceback available>",
            "",
            "Recent application log",
            "----------------------",
            self._read_log_tail(),
            "",
        ]
        return "\n".join(lines)

    def _read_log_tail(self) -> str:
        for handler in self._logger.handlers:
            try:
                handler.flush()
            except (AttributeError, OSError):
                continue
        try:
            lines = self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return "<application log unavailable>"
        return "\n".join(lines[-_LOG_TAIL_LINES:]) or "<application log is empty>"

    def _ensure_directories(self) -> None:
        try:
            self.report_directory.mkdir(parents=True, exist_ok=True)
            self.native_fault_directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=self.report_directory):
                pass
            with tempfile.NamedTemporaryFile(dir=self.native_fault_directory):
                pass
        except OSError:
            self.report_directory = Path(tempfile.gettempdir()) / APP_ID / "logs" / "Crash Reports"
            self.native_fault_directory = self.report_directory / "Native Faults"
            self.report_directory.mkdir(parents=True, exist_ok=True)
            self.native_fault_directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=self.report_directory):
                pass
            with tempfile.NamedTemporaryFile(dir=self.native_fault_directory):
                pass

    def _prune_acknowledged_reports(self) -> None:
        reports = sorted(
            (
                path
                for path in self.report_directory.glob("starflight-crash-*.txt")
                if not path.name.endswith(".pending.txt")
            ),
            key=_modified_time_ns,
            reverse=True,
        )
        for path in reports[_REPORT_LIMIT:]:
            try:
                path.unlink()
            except OSError:
                self._logger.exception("old crash report could not be removed")


def _safe_app_version() -> str:
    try:
        return app_version()
    except Exception:
        return "unknown"


def _qt_versions() -> tuple[str, str]:
    try:
        pyside_version = importlib.metadata.version("PySide6")
    except importlib.metadata.PackageNotFoundError:
        pyside_version = "unavailable"

    qt_core = sys.modules.get("PySide6.QtCore")
    q_version = getattr(qt_core, "qVersion", None)
    if callable(q_version):
        try:
            return str(q_version()), pyside_version
        except Exception:
            pass
    return "not loaded", pyside_version


__all__ = ["CrashReport", "CrashReporter"]
