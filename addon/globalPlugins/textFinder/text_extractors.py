from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree


PLAIN_TEXT_EXTENSIONS = {
	".txt",
	".log",
	".md",
	".csv",
	".ini",
	".json",
	".xml",
	".css",
	".js",
	".py",
}


# Single source of truth for the file types Text Finder can search. Each entry
# is a (display label, tuple of file extensions). The settings panel builds its
# file-type list from this, and the search engine builds its default file
# filters from this, so adding a new supported type only needs one change here.
SUPPORTED_FILE_TYPES = (
	("Plain text and logs (.txt, .log)", (".txt", ".log")),
	("Markdown (.md)", (".md",)),
	("Comma separated values (.csv)", (".csv",)),
	("Configuration files (.ini)", (".ini",)),
	("JSON (.json)", (".json",)),
	("XML (.xml)", (".xml",)),
	("Web pages (.html, .htm)", (".html", ".htm")),
	("Style sheets (.css)", (".css",)),
	("JavaScript (.js)", (".js",)),
	("Python (.py)", (".py",)),
	("Word documents (.docx)", (".docx",)),
	("Rich text (.rtf)", (".rtf",)),
	("OpenDocument text (.odt)", (".odt",)),
	("Excel workbooks (.xlsx)", (".xlsx",)),
	("PowerPoint presentations (.pptx)", (".pptx",)),
	("PDF documents (.pdf)", (".pdf",)),
)


def all_supported_extensions() -> tuple[str, ...]:
	extensions: list[str] = []
	for _label, type_extensions in SUPPORTED_FILE_TYPES:
		extensions.extend(type_extensions)
	return tuple(extensions)


@dataclass(frozen=True)
class ExtractedText:
	text: str
	page_offsets: tuple[tuple[int, int], ...] = ()

	def page_for_offset(self, offset: int) -> int | None:
		for page, page_offset in reversed(self.page_offsets):
			if offset >= page_offset:
				return page
		return None


class TextExtractionError(Exception):
	def __init__(self, reason: str, message: str):
		super().__init__(message)
		self.reason = reason
		self.message = message


def extract_text(path: Path, allow_text_fallback: bool = False) -> ExtractedText:
	extension = path.suffix.lower()
	if extension in PLAIN_TEXT_EXTENSIONS:
		return extract_plain_text(path)
	if extension in {".html", ".htm"}:
		return ExtractedText(visible_html_text(read_text_file(path)))
	if extension == ".docx":
		return extract_docx(path)
	if extension == ".rtf":
		return ExtractedText(rtf_to_text(read_text_file(path)))
	if extension == ".odt":
		return extract_odt(path)
	if extension == ".xlsx":
		return extract_xlsx(path)
	if extension == ".pptx":
		return extract_pptx(path)
	if extension == ".pdf":
		return extract_pdf(path)
	if allow_text_fallback and looks_like_text_file(path):
		return extract_plain_text(path)
	raise TextExtractionError("unsupported", "Unsupported file type.")



def looks_like_text_file(path: Path, sample_size: int = 4096) -> bool:
	try:
		sample = path.read_bytes()[:sample_size]
	except OSError:
		return False
	if not sample:
		return True
	if b"\x00" in sample:
		return False
	control_bytes = 0
	for byte in sample:
		if byte in (9, 10, 12, 13):
			continue
		if byte < 32 or byte == 127:
			control_bytes += 1
	return control_bytes / len(sample) < 0.05

def extract_plain_text(path: Path) -> ExtractedText:
	return ExtractedText(read_text_file(path))


def read_text_file(path: Path) -> str:
	for encoding in ("utf-8-sig", "utf-16", "cp1252"):
		try:
			text = path.read_text(encoding=encoding)
			if text:
				return text
		except UnicodeError:
			continue
	if path.stat().st_size == 0:
		raise TextExtractionError("empty", "File is empty.")
	return path.read_text(encoding="utf-8", errors="replace")


def extract_docx(path: Path) -> ExtractedText:
	try:
		return extract_docx_from_zip(path)
	except PermissionError:
		return extract_docx_from_locked_file(path)


def extract_docx_from_zip(path: Path) -> ExtractedText:
	try:
		with zipfile.ZipFile(path) as archive:
			xml = archive.read("word/document.xml")
	except KeyError as exc:
		raise TextExtractionError("empty", "DOCX document text was not found.") from exc
	except zipfile.BadZipFile as exc:
		raise TextExtractionError("unreadable", "DOCX file is not a valid zip document.") from exc
	return extract_docx_from_document_xml(xml)


def extract_docx_from_document_xml(xml: bytes | str) -> ExtractedText:
	root = ElementTree.fromstring(xml)
	namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
	paragraphs = []
	for paragraph in root.findall(".//w:p", namespace):
		parts = []
		for node in paragraph.iter():
			tag = node.tag.rsplit("}", 1)[-1]
			if tag == "t" and node.text:
				parts.append(node.text)
			elif tag == "tab":
				parts.append("\t")
			elif tag == "br":
				parts.append("\n")
		paragraphs.append("".join(parts))
	text = "\n".join(paragraphs)
	if not text.strip():
		raise TextExtractionError("empty", "No extractable text found.")
	return ExtractedText(text)


def extract_docx_from_locked_file(path: Path) -> ExtractedText:
	try:
		with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_file:
			temp_path = Path(temp_file.name)
		shutil.copyfile(path, temp_path)
		try:
			return extract_docx_from_zip(temp_path)
		finally:
			try:
				temp_path.unlink()
			except OSError:
				pass
	except Exception:
		pass
	return extract_docx_with_powershell(path)


def extract_docx_with_powershell(path: Path) -> ExtractedText:
	command = DOCX_POWERSHELL_READER.format(path=str(path).replace("'", "''"))
	last_error = None
	for executable in powershell_executables():
		try:
			completed = subprocess.run(
				[executable, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
				capture_output=True,
				text=True,
				encoding="utf-8",
				errors="replace",
				timeout=30,
				creationflags=get_hidden_process_flags(),
			)
		except FileNotFoundError as exc:
			last_error = exc
			continue
		except Exception as exc:
			raise TextExtractionError("unreadable", f"DOCX file could not be read while open in Word: {exc}") from exc
		if completed.returncode != 0:
			reason = completed.stderr.strip() or completed.stdout.strip() or "PowerShell could not read the DOCX file."
			raise TextExtractionError("unreadable", reason)
		return extract_docx_from_document_xml(completed.stdout)
	raise TextExtractionError("unreadable", f"DOCX file could not be read while open in Word: {last_error}")


def powershell_executables() -> tuple[str, ...]:
	windows_dir = os.environ.get("SystemRoot") or os.environ.get("windir") or r"C:\Windows"
	return (
		str(Path(windows_dir) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
		str(Path(windows_dir) / "Sysnative" / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
		"powershell.exe",
	)


def get_hidden_process_flags() -> int:
	return getattr(subprocess, "CREATE_NO_WINDOW", 0)


DOCX_POWERSHELL_READER = r'''
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
$fileStream = [System.IO.File]::Open(
	'{path}',
	[System.IO.FileMode]::Open,
	[System.IO.FileAccess]::Read,
	[System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
)
try {{
	$zip = New-Object System.IO.Compression.ZipArchive($fileStream, [System.IO.Compression.ZipArchiveMode]::Read, $true)
	try {{
		$entry = $zip.GetEntry('word/document.xml')
		if ($null -eq $entry) {{ throw 'DOCX document text was not found.' }}
		$reader = New-Object System.IO.StreamReader($entry.Open(), [System.Text.Encoding]::UTF8)
		try {{ $reader.ReadToEnd() }} finally {{ $reader.Dispose() }}
	}} finally {{
		$zip.Dispose()
	}}
}} finally {{
	$fileStream.Dispose()
}}
'''


def extract_odt(path: Path) -> ExtractedText:
	try:
		with zipfile.ZipFile(path) as archive:
			xml = archive.read("content.xml")
	except KeyError as exc:
		raise TextExtractionError("empty", "ODT document text was not found.") from exc
	except zipfile.BadZipFile as exc:
		raise TextExtractionError("unreadable", "ODT file is not a valid zip document.") from exc
	root = ElementTree.fromstring(xml)
	paragraphs = []
	for element in root.iter():
		if element.text:
			paragraphs.append(element.text)
	text = "\n".join(part.strip() for part in paragraphs if part.strip())
	if not text:
		raise TextExtractionError("empty", "No extractable text found.")
	return ExtractedText(text)


def _local_tag(element) -> str:
	return element.tag.rsplit("}", 1)[-1]


def _ordered_zip_members(archive: zipfile.ZipFile, prefix: str, suffix: str) -> list[str]:
	# Office stores sheets and slides as sheet1.xml, sheet2.xml, slide1.xml and so
	# on. The zip directory order is not guaranteed, so sort by the trailing
	# number to keep workbook and presentation order stable.
	members = [name for name in archive.namelist() if name.startswith(prefix) and name.endswith(suffix)]

	def sort_key(name: str) -> tuple[int, str]:
		digits = re.findall(r"(\d+)", name.rsplit("/", 1)[-1])
		return (int(digits[-1]) if digits else 0, name)

	return sorted(members, key=sort_key)


def extract_xlsx(path: Path) -> ExtractedText:
	try:
		archive = zipfile.ZipFile(path)
	except zipfile.BadZipFile as exc:
		raise TextExtractionError("unreadable", "Excel file is not a valid zip document.") from exc
	parts: list[str] = []
	try:
		with archive:
			# Shared strings hold the text content for most workbooks.
			if "xl/sharedStrings.xml" in archive.namelist():
				shared_root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
				for node in shared_root.iter():
					if _local_tag(node) == "t" and node.text:
						parts.append(node.text)
			# Some workbooks store text inline in the worksheets instead.
			for member in _ordered_zip_members(archive, "xl/worksheets/", ".xml"):
				try:
					sheet_root = ElementTree.fromstring(archive.read(member))
				except ElementTree.ParseError:
					continue
				for is_node in sheet_root.iter():
					if _local_tag(is_node) != "is":
						continue
					for text_node in is_node.iter():
						if _local_tag(text_node) == "t" and text_node.text:
							parts.append(text_node.text)
	except KeyError as exc:
		raise TextExtractionError("empty", "Excel workbook text was not found.") from exc
	text = "\n".join(part for part in parts if part.strip())
	if not text.strip():
		raise TextExtractionError("empty", "No extractable text found.")
	return ExtractedText(text)


def extract_pptx(path: Path) -> ExtractedText:
	try:
		archive = zipfile.ZipFile(path)
	except zipfile.BadZipFile as exc:
		raise TextExtractionError("unreadable", "PowerPoint file is not a valid zip document.") from exc
	slides: list[str] = []
	try:
		with archive:
			for member in _ordered_zip_members(archive, "ppt/slides/slide", ".xml"):
				try:
					slide_root = ElementTree.fromstring(archive.read(member))
				except ElementTree.ParseError:
					continue
				runs = [node.text for node in slide_root.iter() if _local_tag(node) == "t" and node.text]
				if runs:
					slides.append(" ".join(runs))
	except KeyError as exc:
		raise TextExtractionError("empty", "PowerPoint slide text was not found.") from exc
	text = "\n".join(slide for slide in slides if slide.strip())
	if not text.strip():
		raise TextExtractionError("empty", "No extractable text found.")
	return ExtractedText(text)


def extract_pdf(path: Path) -> ExtractedText:
	try:
		from pypdf import PdfReader
	except Exception as exc:
		raise TextExtractionError("unsupported", "PDF text extraction is not available in this installation.") from exc
	try:
		reader = PdfReader(str(path))
		parts = []
		page_offsets = []
		for index, page in enumerate(reader.pages, start=1):
			page_offsets.append((index, sum(len(part) for part in parts)))
			parts.append(page.extract_text() or "")
			parts.append("\n")
	except Exception as exc:
		raise TextExtractionError("unreadable", f"PDF could not be read: {exc}") from exc
	text = "".join(parts)
	if not text.strip():
		raise TextExtractionError("empty", "No extractable text found.")
	return ExtractedText(text, tuple(page_offsets))


class VisibleTextHTMLParser(HTMLParser):
	def __init__(self):
		super().__init__()
		self.parts: list[str] = []
		self.skip_depth = 0

	def handle_starttag(self, tag, attrs):
		if tag in {"script", "style"}:
			self.skip_depth += 1
		if tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
			self.parts.append("\n")

	def handle_endtag(self, tag):
		if tag in {"script", "style"} and self.skip_depth:
			self.skip_depth -= 1
		if tag in {"p", "div", "li", "tr"}:
			self.parts.append("\n")

	def handle_data(self, data):
		if not self.skip_depth:
			self.parts.append(data)

	def text(self):
		return html.unescape("".join(self.parts))


def visible_html_text(source: str) -> str:
	parser = VisibleTextHTMLParser()
	parser.feed(source)
	text = parser.text()
	if not text.strip():
		raise TextExtractionError("empty", "No visible text found.")
	return text


def rtf_to_text(source: str) -> str:
	source = re.sub(r"\\par[d]?", "\n", source)
	source = re.sub(r"\\tab", "\t", source)
	source = re.sub(r"\\'[0-9a-fA-F]{2}", "", source)
	source = re.sub(r"\\[a-zA-Z]+\d* ?", "", source)
	source = source.replace("{", "").replace("}", "")
	text = source.strip()
	if not text:
		raise TextExtractionError("empty", "No extractable text found.")
	return text
