from __future__ import annotations

from pathlib import Path

from src.gui_support import (
    UserSettings,
    default_output_path_for_input,
    default_settings_path,
    detect_ddjvu,
    load_settings,
    save_settings,
)


def test_settings_round_trip(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"

    save_settings(UserSettings(ddjvu_path=r"C:\Tools\ddjvu.exe"), settings_path)

    assert load_settings(settings_path) == UserSettings(ddjvu_path=r"C:\Tools\ddjvu.exe")


def test_missing_or_corrupt_settings_fall_back_to_defaults(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.json"
    corrupt_path = tmp_path / "settings.json"
    corrupt_path.write_text("{not json", encoding="utf-8")

    assert load_settings(missing_path) == UserSettings()
    assert load_settings(corrupt_path) == UserSettings()


def test_default_settings_path_uses_appdata() -> None:
    path = default_settings_path({"APPDATA": r"C:\Users\Alice\AppData\Roaming"})

    assert path == Path(r"C:\Users\Alice\AppData\Roaming\DjvuToPdfConverter\settings.json")


def test_default_output_path_for_input_uses_same_folder_and_basename() -> None:
    assert default_output_path_for_input(r"K:\Library\melashchenko.djvu") == str(
        Path(r"K:\Library\melashchenko.pdf")
    )
    assert default_output_path_for_input(r"K:\Library\book.djv") == str(Path(r"K:\Library\book.pdf"))


def test_detect_ddjvu_prefers_saved_path(tmp_path: Path) -> None:
    saved = tmp_path / "saved" / "ddjvu.exe"
    saved.parent.mkdir()
    saved.write_bytes(b"exe")
    path_ddjvu = tmp_path / "path" / "ddjvu.exe"
    common_ddjvu = tmp_path / "common" / "ddjvu.exe"

    result = detect_ddjvu(
        saved,
        path_lookup=lambda name: str(path_ddjvu),
        common_paths=(common_ddjvu,),
    )

    assert result == saved


def test_detect_ddjvu_falls_back_to_path_then_common_paths(tmp_path: Path) -> None:
    path_ddjvu = tmp_path / "path" / "ddjvu.exe"
    common_ddjvu = tmp_path / "common" / "ddjvu.exe"
    common_ddjvu.parent.mkdir()
    common_ddjvu.write_bytes(b"exe")

    assert (
        detect_ddjvu(
            tmp_path / "missing.exe",
            path_lookup=lambda name: str(path_ddjvu),
            common_paths=(common_ddjvu,),
        )
        == path_ddjvu
    )
    assert (
        detect_ddjvu(
            tmp_path / "missing.exe",
            path_lookup=lambda name: None,
            common_paths=(common_ddjvu,),
        )
        == common_ddjvu
    )
