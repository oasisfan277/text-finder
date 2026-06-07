from __future__ import annotations

import configparser
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = ROOT / "addon"
DIST_DIR = ROOT / "dist"


def read_manifest() -> tuple[str, str]:
	manifest = configparser.ConfigParser()
	manifest.optionxform = str
	with (ADDON_DIR / "manifest.ini").open(encoding="utf-8") as manifest_file:
		manifest.read_string("[addon]\n" + manifest_file.read())
	name = manifest["addon"]["name"].strip().strip('"')
	version = manifest["addon"]["version"].strip().strip('"')
	return name, version


def should_package(path: Path) -> bool:
	parts = set(path.parts)
	if "__pycache__" in parts:
		return False
	return path.suffix.lower() not in {".pyc", ".pyo"}


def build_package() -> Path:
	name, version = read_manifest()
	DIST_DIR.mkdir(exist_ok=True)
	output = DIST_DIR / f"{name}-{version}.nvda-addon"
	if output.exists():
		output.unlink()
	with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
		for path in ADDON_DIR.rglob("*"):
			relative = path.relative_to(ADDON_DIR)
			if path.is_file() and should_package(relative):
				archive.write(path, relative.as_posix())
	return output


def clean() -> None:
	if DIST_DIR.exists():
		shutil.rmtree(DIST_DIR)


if __name__ == "__main__":
	package = build_package()
	print(package)
