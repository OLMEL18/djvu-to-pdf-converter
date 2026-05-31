from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Callable

from PIL import Image, ImageSequence

from .djvu_tools import DjvuToolError, Runner, discover_tools, get_page_count, render_page


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

    temp_dir = Path(tempfile.mkdtemp(prefix="djvu_to_pdf_"))
    rendered_pages: list[Path] = []
    try:
        page_count = get_page_count(input_file, tools.djvused, runner=runner)
        _report(progress, 0, page_count, f"Found {page_count} page(s).")

        for page_number in range(1, page_count + 1):
            image_path = temp_dir / f"page_{page_number:06d}.tif"
            _report(progress, page_number - 1, page_count, f"Rendering page {page_number}...")
            render_page(
                input_file,
                image_path,
                page_number,
                tools.ddjvu,
                dpi=options.dpi,
                scale=options.scale,
                runner=runner,
            )
            rendered_pages.append(image_path)
            _report(progress, page_number, page_count, f"Rendered page {page_number}.")

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

    images: list[Image.Image] = []
    try:
        for image_path in image_paths:
            with Image.open(image_path) as source:
                # Copy frames so Pillow can close the temporary TIFF files before PDF writing.
                for frame in ImageSequence.Iterator(source):
                    images.append(frame.convert("RGB").copy())

        first, rest = images[0], images[1:]
        save_kwargs: dict[str, object] = {
            "save_all": True,
            "append_images": rest,
            "quality": quality,
        }
        if dpi is not None:
            save_kwargs["resolution"] = float(dpi)
        first.save(output_file, "PDF", **save_kwargs)
    finally:
        for image in images:
            image.close()


def _report(progress: ProgressCallback | None, current: int, total: int, message: str) -> None:
    if progress:
        progress(current, total, message)

