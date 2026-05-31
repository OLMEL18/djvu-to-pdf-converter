from __future__ import annotations

import argparse
import sys

from .converter import ConversionError, ConversionOptions, convert_djvu_to_pdf


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert a DJVU/DJV file to an image-based PDF.")
    parser.add_argument("input", help="Input .djvu or .djv file")
    parser.add_argument("output", help="Output .pdf file")
    parser.add_argument("--quality", type=int, default=90, help="JPEG quality for PDF pages (1-100, default: 90)")
    parser.add_argument("--dpi", type=int, help="Render pages at the requested DPI when supported by ddjvu")
    parser.add_argument("--scale", type=int, help="Render pages with ddjvu scale percent")
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary rendered page images")
    parser.add_argument("--ddjvu-path", help="Explicit path to ddjvu.exe or ddjvu")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    options = ConversionOptions(
        quality=args.quality,
        dpi=args.dpi,
        scale=args.scale,
        keep_temp=args.keep_temp,
        ddjvu_path=args.ddjvu_path,
    )

    def log(current: int, total: int, message: str) -> None:
        prefix = f"[{current}/{total}] " if total else ""
        print(f"{prefix}{message}")

    try:
        convert_djvu_to_pdf(args.input, args.output, options, progress=log)
    except ConversionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

