# DJVU to PDF Converter

Simple offline DJVU/DJV to image-based PDF converter for Windows first, written in Python with a small CLI and `tkinter` GUI.

The MVP uses local DjVuLibre command-line tools. It does not upload files, does not call cloud services, and does not implement a DJVU decoder from scratch.

## Requirements

- Python 3.11+
- DjVuLibre installed locally, with `ddjvu` and `djvused` available on `PATH`
- Python dependencies from `requirements.txt`

On Windows, you can also pass the full path to `ddjvu.exe`. The app will look for `djvused.exe` beside it first, then on `PATH`.

## Install

```powershell
python -m pip install -r requirements.txt
```

For tests:

```powershell
python -m pip install -r requirements-dev.txt
```

## CLI Usage

```powershell
python -m src.cli "C:\Books\input.djvu" "C:\Books\output.pdf"
```

With options:

```powershell
python -m src.cli "C:\Books\input.djvu" "C:\Books\output.pdf" --quality 90 --dpi 300 --ddjvu-path "C:\Program Files\DjVuLibre\ddjvu.exe"
```

Options:

- `--quality`: JPEG quality for PDF pages, default `90`
- `--dpi`: pass a target DPI to `ddjvu`
- `--scale`: pass a render scale percentage to `ddjvu`
- `--keep-temp`: keep rendered temporary TIFF files for debugging
- `--ddjvu-path`: explicit path to `ddjvu.exe`
- `--render-format`: primary render format, one of `tiff`, `ppm`, or `pnm`; default `tiff`
- `--fallback-formats`: comma-separated formats to try if a page render fails; default `tiff,ppm,pnm`
- `--temp-dir`: parent folder for conversion temporary folders, useful when PPM/PNM output is large

Use either `--dpi` or `--scale`, not both.

The default conversion starts with TIFF and automatically falls back to PPM, then PNM, for individual page render failures:

```powershell
python -m src.cli "input.djvu" "output.pdf" --fallback-formats tiff,ppm,pnm
```

Emergency direct PPM mode:

```powershell
python -m src.cli "input.djvu" "output.pdf" --render-format ppm
```

## GUI Usage

```powershell
python -m src.gui
```

Choose an input DJVU/DJV file, choose the output PDF path, optionally provide `ddjvu.exe`, then select **Convert**.

## Validation

```powershell
python -m compileall src
python -m pytest
python -m src.cli --help
python -m src.gui
```

The GUI command opens a local desktop window and runs fully offline.

## Packaging

Optional Windows `.exe` build with PyInstaller:

```powershell
python -m pip install pyinstaller
python -m PyInstaller --noconsole --name djvu-to-pdf-converter --version-file packaging\windows\version_info.txt src\gui.py
```

Windows executable metadata is prepared in `packaging/windows/version_info.txt` for future PyInstaller builds. This repository does not include a ready-built EXE.

DjVuLibre binaries are not bundled in this MVP. Review DjVuLibre licensing before distributing any bundled copy. For now, users should install DjVuLibre themselves or provide the path to `ddjvu.exe`.

## Troubleshooting

### TIFFAppendToStrip / Error while flushing tiff file

Some DJVU pages can fail when `ddjvu` writes TIFF output, even when the page itself is readable. The converter now retries failed pages with fallback render formats by default.

Recommended command:

```powershell
python -m src.cli "input.djvu" "output.pdf" --fallback-formats tiff,ppm,pnm
```

If TIFF continues to fail or you want to avoid it entirely, start with PPM:

```powershell
python -m src.cli "input.djvu" "output.pdf" --render-format ppm
```

For very large files, put temporary images on a drive with enough free space:

```powershell
python -m src.cli "input.djvu" "output.pdf" --render-format ppm --temp-dir "D:\Temp\djvu_temp"
```

Use any local folder with enough free space for `--temp-dir`; PPM/PNM intermediate files can be large.

### ddjvu was not found on PATH

Install DjVuLibre locally and make sure `ddjvu` and `djvused` are available on `PATH`, or pass the full path to `ddjvu.exe`:

```powershell
python -m src.cli "input.djvu" "output.pdf" --ddjvu-path "C:\Program Files\DjVuLibre\ddjvu.exe"
```

## Notes

- Output PDFs are image-based.
- Output PDFs can be much larger than the original DJVU, especially when fallback rendering uses PPM/PNM intermediates.
- Hidden OCR/text layers from DJVU files are not preserved in this MVP.
- File paths with spaces and Unicode/Cyrillic characters are supported by passing subprocess arguments as arrays.

## TODO

- Add searchable PDF output by extracting OCR/text where available.
- Add an explicit `djvused` path option if users need separate tool locations.
- Add cross-platform packaging notes for macOS and Linux.
- Add integration tests using generated or freely licensed fixture inputs.

## License

MIT License. See `LICENSE`.
