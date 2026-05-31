from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from src.converter import ConversionError, ConversionOptions, validate_options, validate_output_path
from src.djvu_tools import DjvuToolError, build_render_page_command, get_page_count, run_command


def test_validate_output_requires_pdf(tmp_path: Path) -> None:
    with pytest.raises(ConversionError, match="pdf"):
        validate_output_path(tmp_path / "book.txt")


def test_validate_options_rejects_dpi_and_scale() -> None:
    with pytest.raises(ConversionError, match="either --dpi or --scale"):
        validate_options(ConversionOptions(dpi=300, scale=100))


def test_build_render_page_command_preserves_paths_with_spaces_and_unicode() -> None:
    command = build_render_page_command(
        Path("C:/Program Files/DjVuLibre/ddjvu.exe"),
        Path("C:/Документы/input file.djvu"),
        Path("C:/Temp/page 001.tif"),
        3,
        dpi=300,
    )

    assert command == [
        "C:\\Program Files\\DjVuLibre\\ddjvu.exe",
        "-format=tiff",
        "-page=3",
        "-dpi=300",
        "C:\\Документы\\input file.djvu",
        "C:\\Temp\\page 001.tif",
    ]


def test_get_page_count_parses_djvused_output() -> None:
    def runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="12\n", stderr="")

    assert get_page_count(Path("input.djvu"), Path("djvused"), runner=runner) == 12


def test_get_page_count_rejects_invalid_output() -> None:
    def runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="nope\n", stderr="")

    with pytest.raises(DjvuToolError, match="Could not parse"):
        get_page_count(Path("input.djvu"), Path("djvused"), runner=runner)


def test_run_command_wraps_failed_process() -> None:
    def runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(2, args[0], stderr="bad page")

    with pytest.raises(DjvuToolError, match="bad page"):
        run_command(["ddjvu", "-bad"], runner=runner)

