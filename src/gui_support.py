from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
from typing import Callable, Mapping


SETTINGS_DIR_NAME = "DjvuToPdfConverter"
SETTINGS_FILE_NAME = "settings.json"
COMMON_WINDOWS_DDJVU_PATHS = (
    Path(r"C:\Program Files (x86)\DjVuLibre\ddjvu.exe"),
    Path(r"C:\Program Files\DjVuLibre\ddjvu.exe"),
)

PathLookup = Callable[[str], str | None]


@dataclass(frozen=True)
class UserSettings:
    ddjvu_path: str = ""


def default_settings_path(environ: Mapping[str, str] | None = None) -> Path:
    env = environ or os.environ
    appdata = env.get("APPDATA")
    if appdata:
        return Path(appdata) / SETTINGS_DIR_NAME / SETTINGS_FILE_NAME
    return Path.home() / "AppData" / "Roaming" / SETTINGS_DIR_NAME / SETTINGS_FILE_NAME


def load_settings(settings_path: str | Path | None = None) -> UserSettings:
    path = Path(settings_path) if settings_path is not None else default_settings_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return UserSettings()

    if not isinstance(raw, dict):
        return UserSettings()
    ddjvu_path = raw.get("ddjvu_path", "")
    return UserSettings(ddjvu_path=ddjvu_path if isinstance(ddjvu_path, str) else "")


def save_settings(settings: UserSettings, settings_path: str | Path | None = None) -> None:
    path = Path(settings_path) if settings_path is not None else default_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"ddjvu_path": settings.ddjvu_path}, indent=2) + "\n",
        encoding="utf-8",
    )


def default_output_path_for_input(input_path: str | Path) -> str:
    return str(Path(input_path).with_suffix(".pdf"))


def detect_ddjvu(
    saved_path: str | Path | None = None,
    *,
    path_lookup: PathLookup = shutil.which,
    common_paths: tuple[Path, ...] = COMMON_WINDOWS_DDJVU_PATHS,
) -> Path | None:
    if saved_path:
        candidate = Path(saved_path).expanduser()
        if candidate.is_file():
            return candidate

    found = path_lookup("ddjvu")
    if found:
        return Path(found)

    for candidate in common_paths:
        if candidate.is_file():
            return candidate
    return None
