from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from src import cli
from src.converter import (
    ConversionError,
    ConversionOptions,
    convert_djvu_to_pdf,
    parse_fallback_formats,
    validate_options,
    validate_output_path,
)
from src.djvu_tools import DjvuToolError, DjvuTools, build_render_page_command, get_page_count, run_command


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
        render_format="tiff",
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


def test_unsupported_fallback_format_is_rejected() -> None:
    with pytest.raises(ConversionError, match="fallback-formats"):
        parse_fallback_formats("tiff,bmp")


def test_unsupported_render_format_is_rejected() -> None:
    with pytest.raises(ConversionError, match="render-format"):
        validate_options(ConversionOptions(render_format="bmp"))


def test_fallback_formats_are_attempted_in_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_file = tmp_path / "book.djvu"
    output_file = tmp_path / "book.pdf"
    input_file.write_bytes(b"fake")
    attempted: list[str] = []
    messages: list[str] = []

    monkeypatch.setattr("src.converter.discover_tools", lambda ddjvu_path=None: DjvuTools(Path("ddjvu"), Path("djvused")))
    monkeypatch.setattr("src.converter.get_page_count", lambda *args, **kwargs: 1)
    monkeypatch.setattr("src.converter.assemble_pdf", lambda image_paths, output, **kwargs: output.write_bytes(b"%PDF"))

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        render_format = next(part.split("=", 1)[1] for part in command if part.startswith("-format="))
        attempted.append(render_format)
        if render_format == "tiff":
            raise subprocess.CalledProcessError(1, command, stderr="Error while flushing tiff file.")
        Path(command[-1]).write_bytes(b"image")
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    convert_djvu_to_pdf(
        input_file,
        output_file,
        ConversionOptions(fallback_formats=("tiff", "ppm", "pnm")),
        runner=runner,
        progress=lambda current, total, message: messages.append(message),
    )

    assert attempted == ["tiff", "ppm"]
    assert any("TIFF render failed, trying PPM" in message for message in messages)
    assert output_file.read_bytes() == b"%PDF"


def test_failure_message_includes_page_number_format_and_attempts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_file = tmp_path / "book.djvu"
    output_file = tmp_path / "book.pdf"
    input_file.write_bytes(b"fake")

    monkeypatch.setattr("src.converter.discover_tools", lambda ddjvu_path=None: DjvuTools(Path("ddjvu"), Path("djvused")))
    monkeypatch.setattr("src.converter.get_page_count", lambda *args, **kwargs: 1)

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, command, stderr="ddjvu stderr text")

    with pytest.raises(ConversionError) as exc_info:
        convert_djvu_to_pdf(
            input_file,
            output_file,
            ConversionOptions(fallback_formats=("tiff", "ppm")),
            runner=runner,
        )

    message = str(exc_info.value)
    assert "page 1" in message
    assert "TIFF" in message
    assert "PPM" in message
    assert "ddjvu stderr text" in message
    assert "Attempted formats: TIFF, PPM" in message


def test_cli_parses_new_options() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "input.djvu",
            "output.pdf",
            "--render-format",
            "ppm",
            "--fallback-formats",
            "ppm,pnm",
            "--temp-dir",
            "K:/Library/djvu_temp",
        ]
    )

    assert args.render_format == "ppm"
    assert args.fallback_formats == "ppm,pnm"
    assert args.temp_dir == "K:/Library/djvu_temp"
