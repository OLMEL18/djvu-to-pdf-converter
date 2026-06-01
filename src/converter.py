from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Callable

import img2pdf
from PIL import Image, ImageSequence

from .djvu_tools import (
    SUPPORTED_RENDER_FORMATS,
    DjvuToolError,
    RenderFormat,
    Runner,
    discover_tools,
    get_page_count,
    render_page,
)


class ConversionError(RuntimeError):
    """Raised for user-facing conversion failures."""


ProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True)
class ConversionOptions:
    quality: int = 90
    dpi: int | None = None
    scale: int | None = None
    keep_temp: bool = False
    ddjvu_path: str | Path | None = None
    render_format: RenderFormat = "tiff"
    fallback_formats: tuple[RenderFormat, ...] = SUPPORTED_RENDER_FORMATS
    temp_dir: str | Path | None = None


def validate_input_path(input_path: str | Path) -> Path:
    path = Path(input_path).expanduser()
    if path.suffix.lower() not in {".djvu", ".djv"}:
        raise ConversionError("Input file must have a .djvu or .djv extension.")
    if not path.is_file():
        raise ConversionError(f"Input file does not exist: {path}")
    return path


def validate_output_path(output_path: str | Path) -> Path:
    path = Path(output_path).expanduser()
    if path.suffix.lower() != ".pdf":
        raise ConversionError("Output file must have a .pdf extension.")
    parent = path.parent if path.parent != Path("") else Path.cwd()
    if not parent.exists():
        raise ConversionError(f"Output folder does not exist: {parent}")
    return path


def validate_options(options: ConversionOptions) -> None:
    if not 1 <= options.quality <= 100:
        raise ConversionError("--quality must be between 1 and 100.")
    if options.dpi is not None and options.dpi <= 0:
        raise ConversionError("--dpi must be a positive integer.")
    if options.scale is not None and options.scale <= 0:
        raise ConversionError("--scale must be a positive integer.")
    if options.dpi is not None and options.scale is not None:
        raise ConversionError("Use either --dpi or --scale, not both.")
    _validate_render_format(options.render_format, "--render-format")
    if not options.fallback_formats:
        raise ConversionError("--fallback-formats must include at least one format.")
    for render_format in options.fallback_formats:
        _validate_render_format(render_format, "--fallback-formats")
    if options.temp_dir is not None:
        temp_root = Path(options.temp_dir).expanduser()
        if temp_root.exists() and not temp_root.is_dir():
            raise ConversionError(f"Temporary path is not a folder: {temp_root}")


def convert_djvu_to_pdf(
    input_path: str | Path,
    output_path: str | Path,
    options: ConversionOptions | None = None,
    *,
    progress: ProgressCallback | None = None,
    runner: Runner = subprocess.run,
) -> Path:
    options = options or ConversionOptions()
    validate_options(options)
    input_file = validate_input_path(input_path)
    output_file = validate_output_path(output_path)

    try:
        tools = discover_tools(options.ddjvu_path)
    except DjvuToolError as exc:
        raise ConversionError(str(exc)) from exc

    temp_root = _prepare_temp_root(options.temp_dir)
    temp_dir = Path(tempfile.mkdtemp(prefix="djvu_to_pdf_", dir=temp_root))
    rendered_pages: list[Path] = []
    try:
        page_count = get_page_count(input_file, tools.djvused, runner=runner)
        _report(progress, 0, page_count, f"Found {page_count} page(s).")
        render_formats = _ordered_render_formats(options)

        for page_number in range(1, page_count + 1):
            _report(progress, page_number - 1, page_count, f"Rendering page {page_number}...")
            image_path, used_format = _render_page_with_fallback(
                input_file,
                page_number,
                temp_dir,
                tools.ddjvu,
                render_formats,
                options,
                progress=progress,
                page_count=page_count,
                runner=runner,
            )
            rendered_pages.append(image_path)
            _report(progress, page_number, page_count, f"Rendered page {page_number} as {used_format.upper()}.")

        _report(progress, page_count, page_count, "Assembling PDF...")
        assemble_pdf(rendered_pages, output_file, quality=options.quality, dpi=options.dpi)
        _report(progress, page_count, page_count, f"Saved PDF: {output_file}")
        return output_file
    except (DjvuToolError, OSError) as exc:
        raise ConversionError(str(exc)) from exc
    finally:
        if options.keep_temp:
            _report(progress, 0, 0, f"Temporary files kept at: {temp_dir}")
        else:
            shutil.rmtree(temp_dir, ignore_errors=True)


def assemble_pdf(image_paths: list[Path], output_file: Path, *, quality: int, dpi: int | None) -> None:
    if not image_paths:
        raise ConversionError("No rendered pages were produced.")

    jpeg_dir = Path(tempfile.mkdtemp(prefix="pdf_pages_", dir=image_paths[0].parent))
    jpeg_pages: list[Path] = []
    try:
        for image_path in image_paths:
            with Image.open(image_path) as source:
                for frame in ImageSequence.Iterator(source):
                    page_number = len(jpeg_pages) + 1
                    jpeg_path = jpeg_dir / f"page_{page_number:06d}.jpg"
                    page = frame.convert("RGB")
                    try:
                        save_kwargs: dict[str, object] = {"quality": quality, "optimize": True}
                        if dpi is not None:
                            save_kwargs["dpi"] = (dpi, dpi)
                        page.save(jpeg_path, "JPEG", **save_kwargs)
                    finally:
                        page.close()
                    jpeg_pages.append(jpeg_path)

        with output_file.open("wb") as pdf_file:
            img2pdf.convert([str(path) for path in jpeg_pages], outputstream=pdf_file)
    finally:
        shutil.rmtree(jpeg_dir, ignore_errors=True)


def _report(progress: ProgressCallback | None, current: int, total: int, message: str) -> None:
    if progress:
        progress(current, total, message)


def _validate_render_format(render_format: str, option_name: str) -> None:
    if render_format not in SUPPORTED_RENDER_FORMATS:
        allowed = ", ".join(SUPPORTED_RENDER_FORMATS)
        raise ConversionError(f"{option_name} must be one of: {allowed}.")


def parse_fallback_formats(value: str) -> tuple[RenderFormat, ...]:
    formats = tuple(part.strip().lower() for part in value.split(",") if part.strip())
    if not formats:
        raise ConversionError("--fallback-formats must include at least one format.")
    for render_format in formats:
        _validate_render_format(render_format, "--fallback-formats")
    return formats


def _ordered_render_formats(options: ConversionOptions) -> tuple[RenderFormat, ...]:
    formats: list[RenderFormat] = [options.render_format]
    formats.extend(render_format for render_format in options.fallback_formats if render_format not in formats)
    return tuple(formats)


def _render_page_with_fallback(
    input_file: Path,
    page_number: int,
    temp_dir: Path,
    ddjvu: Path,
    render_formats: tuple[RenderFormat, ...],
    options: ConversionOptions,
    *,
    progress: ProgressCallback | None,
    page_count: int,
    runner: Runner,
) -> tuple[Path, RenderFormat]:
    failures: list[tuple[RenderFormat, str]] = []

    for index, render_format in enumerate(render_formats):
        image_path = temp_dir / f"page_{page_number:06d}.{_extension_for_format(render_format)}"
        try:
            render_page(
                input_file,
                image_path,
                page_number,
                ddjvu,
                render_format=render_format,
                dpi=options.dpi,
                scale=options.scale,
                runner=runner,
            )
            return image_path, render_format
        except DjvuToolError as exc:
            failures.append((render_format, str(exc)))
            if index < len(render_formats) - 1:
                next_format = render_formats[index + 1]
                _report(
                    progress,
                    page_number,
                    page_count,
                    f"{render_format.upper()} render failed, trying {next_format.upper()}...",
                )
                continue
            attempted = ", ".join(render_format.upper() for render_format, _ in failures)
            details = "\n".join(f"- {render_format.upper()}: {message}" for render_format, message in failures)
            raise DjvuToolError(
                f"Failed to render page {page_number}. Attempted formats: {attempted}.\n{details}"
            ) from exc

    raise DjvuToolError(f"Failed to render page {page_number}. No render formats were attempted.")


def _extension_for_format(render_format: RenderFormat) -> str:
    return "tif" if render_format == "tiff" else render_format


def _prepare_temp_root(temp_dir: str | Path | None) -> Path | None:
    if temp_dir is None:
        return None
    temp_root = Path(temp_dir).expanduser()
    try:
        temp_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConversionError(f"Could not create temporary folder: {temp_root}") from exc
    if not temp_root.is_dir():
        raise ConversionError(f"Temporary path is not a folder: {temp_root}")
    return temp_root
