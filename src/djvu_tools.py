from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
from typing import Callable, Sequence


class DjvuToolError(RuntimeError):
    """Raised when a DjVuLibre command-line tool is missing or fails."""


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class DjvuTools:
    ddjvu: Path
    djvused: Path


def resolve_executable(name: str, explicit_path: str | Path | None = None) -> Path:
    """Resolve an executable from an explicit path or PATH."""
    if explicit_path:
        candidate = Path(explicit_path).expanduser()
        if candidate.is_file():
            return candidate
        raise DjvuToolError(f"{name} was not found at: {candidate}")

    found = shutil.which(name)
    if found:
        return Path(found)
    raise DjvuToolError(f"{name} was not found on PATH.")


def resolve_sibling_or_path(name: str, sibling_of: Path) -> Path:
    suffix = sibling_of.suffix
    sibling = sibling_of.with_name(f"{name}{suffix}")
    if sibling.is_file():
        return sibling
    return resolve_executable(name)


def discover_tools(ddjvu_path: str | Path | None = None) -> DjvuTools:
    ddjvu = resolve_executable("ddjvu", ddjvu_path)
    djvused = resolve_sibling_or_path("djvused", ddjvu)
    return DjvuTools(ddjvu=ddjvu, djvused=djvused)


def build_page_count_command(djvused: Path, input_file: Path) -> list[str]:
    return [str(djvused), "-e", "n", str(input_file)]


def build_render_page_command(
    ddjvu: Path,
    input_file: Path,
    output_file: Path,
    page_number: int,
    *,
    dpi: int | None = None,
    scale: int | None = None,
) -> list[str]:
    command = [
        str(ddjvu),
        "-format=tiff",
        f"-page={page_number}",
    ]
    if dpi is not None:
        command.append(f"-dpi={dpi}")
    if scale is not None:
        command.append(f"-scale={scale}")
    command.extend([str(input_file), str(output_file)])
    return command


def run_command(
    command: Sequence[str],
    *,
    runner: Runner = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    try:
        return runner(
            list(command),
            check=True,
            capture_output=True,
            text=True,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise DjvuToolError(f"Tool not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        message = f"Command failed: {' '.join(command)}"
        if detail:
            message = f"{message}\n{detail}"
        raise DjvuToolError(message) from exc


def get_page_count(
    input_file: Path,
    djvused: Path,
    *,
    runner: Runner = subprocess.run,
) -> int:
    result = run_command(build_page_count_command(djvused, input_file), runner=runner)
    raw = result.stdout.strip()
    try:
        count = int(raw)
    except ValueError as exc:
        raise DjvuToolError(f"Could not parse page count from djvused output: {raw!r}") from exc
    if count < 1:
        raise DjvuToolError(f"DjVu file reported an invalid page count: {count}")
    return count


def render_page(
    input_file: Path,
    output_file: Path,
    page_number: int,
    ddjvu: Path,
    *,
    dpi: int | None = None,
    scale: int | None = None,
    runner: Runner = subprocess.run,
) -> None:
    command = build_render_page_command(
        ddjvu,
        input_file,
        output_file,
        page_number,
        dpi=dpi,
        scale=scale,
    )
    try:
        run_command(command, runner=runner)
    except DjvuToolError as exc:
        raise DjvuToolError(f"Failed to render page {page_number}: {exc}") from exc

