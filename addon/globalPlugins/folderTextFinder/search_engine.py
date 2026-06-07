from __future__ import annotations

import fnmatch
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from .text_extractors import ExtractedText, TextExtractionError, extract_text


@dataclass(frozen=True)
class SearchOptions:
	query: str
	whole_word: bool = False
	case_sensitive: bool = False
	include_subfolders: bool = False
	file_patterns: tuple[str, ...] = ("*",)
	max_file_size: int = 25 * 1024 * 1024
	report_page_numbers: bool = True


@dataclass(frozen=True)
class SearchResult:
	path: Path
	line: int
	column: int
	preview: str
	page: int | None = None

	def format_location(self) -> str:
		if self.page is not None:
			return f"Page {self.page}, Line {self.line}, Column {self.column}"
		return f"Line {self.line}, Column {self.column}"


@dataclass
class SearchStatistics:
	folder: Path
	options: SearchOptions
	duration: float = 0.0
	matches_found: int = 0
	files_with_matches: set[Path] = field(default_factory=set)
	supported_files_searched: int = 0
	unsupported_files: list[tuple[Path, str]] = field(default_factory=list)
	no_extractable_text_files: list[tuple[Path, str]] = field(default_factory=list)
	unreadable_files: list[tuple[Path, str]] = field(default_factory=list)

	def summary_message(self) -> str:
		if self.matches_found:
			start = f"Search complete. {self.matches_found} matches found in {len(self.files_with_matches)} files."
		else:
			start = "Search complete. No matches found."
		return (
			f"{start} {self.supported_files_searched} supported files searched. "
			f"{len(self.unsupported_files)} unsupported files skipped. "
			f"{len(self.no_extractable_text_files)} files contained no extractable text. "
			f"{len(self.unreadable_files)} files could not be read."
		)

	def to_report(self) -> str:
		lines = [
			"Folder Text Finder Statistics",
			"",
			f"Search folder: {self.folder}",
			f"Include subfolders: {'yes' if self.options.include_subfolders else 'no'}",
			f"Search mode: {'exact whole word' if self.options.whole_word else 'exact fragment'}",
			f"Case sensitive: {'yes' if self.options.case_sensitive else 'no'}",
			f"Search text length: {len(self.options.query)}",
			f"Matches found: {self.matches_found}",
			f"Files containing matches: {len(self.files_with_matches)}",
			f"Supported files searched: {self.supported_files_searched}",
			f"Unsupported files skipped: {len(self.unsupported_files)}",
			f"Files with no extractable text: {len(self.no_extractable_text_files)}",
			f"Unreadable files: {len(self.unreadable_files)}",
			f"Total search duration: {self.duration:.2f} seconds",
		]
		self._append_file_section(lines, "Unsupported Files", self.unsupported_files)
		self._append_file_section(lines, "Files Without Extractable Text", self.no_extractable_text_files)
		self._append_file_section(lines, "Unreadable Files", self.unreadable_files)
		return "\n".join(lines)

	def _append_file_section(self, lines: list[str], title: str, entries: list[tuple[Path, str]]) -> None:
		if not entries:
			return
		lines.extend(["", title])
		for path, reason in entries:
			lines.extend([str(path), f"Reason: {reason}", ""])


class Searcher:
	def __init__(self, folder: Path, options: SearchOptions):
		self.folder = folder
		self.options = options

	def search(self) -> tuple[list[SearchResult], SearchStatistics]:
		started = time.monotonic()
		statistics = SearchStatistics(self.folder, self.options)
		results: list[SearchResult] = []
		for path in self._iter_candidate_files():
			if not self._matches_patterns(path):
				statistics.unsupported_files.append((path, "File does not match the selected file filters."))
				continue
			try:
				if path.stat().st_size > self.options.max_file_size:
					statistics.unreadable_files.append((path, "File is larger than the configured maximum size."))
					continue
				extracted = extract_text(path)
			except TextExtractionError as exc:
				if exc.reason == "unsupported":
					statistics.unsupported_files.append((path, exc.message))
				elif exc.reason == "empty":
					statistics.no_extractable_text_files.append((path, exc.message))
				else:
					statistics.unreadable_files.append((path, exc.message))
				continue
			except OSError as exc:
				statistics.unreadable_files.append((path, str(exc)))
				continue
			statistics.supported_files_searched += 1
			file_results = list(find_matches(path, extracted, self.options))
			results.extend(file_results)
			if file_results:
				statistics.files_with_matches.add(path)
				statistics.matches_found += len(file_results)
		statistics.duration = time.monotonic() - started
		return results, statistics

	def _iter_candidate_files(self):
		if self.options.include_subfolders:
			yield from (path for path in self.folder.rglob("*") if path.is_file())
		else:
			yield from (path for path in self.folder.iterdir() if path.is_file())

	def _matches_patterns(self, path: Path) -> bool:
		return any(fnmatch.fnmatch(path.name.lower(), pattern.lower()) for pattern in self.options.file_patterns)


def find_matches(path: Path, extracted: ExtractedText, options: SearchOptions):
	text = extracted.text
	query = options.query
	if not options.case_sensitive:
		search_text = text.casefold()
		search_query = query.casefold()
	else:
		search_text = text
		search_query = query

	if options.whole_word:
		spans = exact_whole_word_spans(search_text, search_query)
	else:
		spans = literal_spans(search_text, search_query)

	for start, end in spans:
		line, column = line_column_for_offset(text, start)
		page = extracted.page_for_offset(start) if options.report_page_numbers else None
		yield SearchResult(path=path, line=line, column=column, preview=preview_for_span(text, start, end), page=page)


def exact_whole_word_spans(text: str, query: str):
	for start, end in literal_spans(text, query):
		before = text[start - 1] if start > 0 else ""
		after = text[end] if end < len(text) else ""
		if not is_word_character(before) and not is_word_character(after):
			yield start, end


def is_word_character(character: str) -> bool:
	return bool(character) and (character.isalnum() or character in "_'\u2019")


def literal_spans(text: str, query: str):
	if not query:
		return
	start = 0
	while True:
		index = text.find(query, start)
		if index == -1:
			return
		yield index, index + len(query)
		start = index + max(len(query), 1)


def line_column_for_offset(text: str, offset: int) -> tuple[int, int]:
	line = text.count("\n", 0, offset) + 1
	line_start = text.rfind("\n", 0, offset) + 1
	column = offset - line_start + 1
	return line, column


def preview_for_span(text: str, start: int, end: int, context: int = 80) -> str:
	sentence_preview = sentence_excerpt_for_span(text, start, end)
	if sentence_preview:
		return render_preview_text(sentence_preview)
	preview_start = max(0, start - context)
	preview_end = min(len(text), end + context)
	return render_preview_text(text[preview_start:preview_end])


def sentence_excerpt_for_span(text: str, start: int, end: int) -> str | None:
	sentence_start, sentence_end = sentence_bounds_for_offset(text, start)
	if sentence_start is None or sentence_end is None:
		return None
	if not is_sentence_like(text[sentence_start:sentence_end]):
		return None
	preview_end = sentence_end
	if word_count(text[sentence_start:sentence_end]) <= 4 and not sentence_ends_with_closing_dialogue(text[sentence_start:sentence_end]):
		next_start, next_end = next_sentence_bounds(text, sentence_end)
		if next_start is not None and next_end is not None:
			preview_end = next_end
	return text[sentence_start:preview_end].strip()


def sentence_bounds_for_offset(text: str, offset: int) -> tuple[int | None, int | None]:
	boundary = offset - 1
	while boundary >= 0 and text[boundary] not in ".!?\r\n":
		boundary -= 1
	start = boundary + 1
	while start < len(text) and text[start].isspace():
		start += 1
	end = offset
	while end < len(text) and text[end] not in ".!?\r\n":
		end += 1
	if end < len(text) and text[end] in ".!?":
		end += 1
	while end < len(text) and text[end] in "'\"\u201d\u2019)]}":
		end += 1
	if start >= end:
		return None, None
	return start, end


def next_sentence_bounds(text: str, offset: int) -> tuple[int | None, int | None]:
	start = offset
	while start < len(text) and text[start].isspace():
		start += 1
	if start >= len(text):
		return None, None
	return sentence_bounds_for_offset(text, start)


def is_sentence_like(excerpt: str) -> bool:
	stripped = excerpt.strip().rstrip("'\"\u201d\u2019)]}")
	return bool(stripped) and stripped[-1:] in ".!?"


def sentence_ends_with_closing_dialogue(excerpt: str) -> bool:
	stripped = excerpt.strip()
	if not stripped or stripped[-1:] not in "'\"\u201d\u2019":
		return False
	stripped = stripped.rstrip("'\"\u201d\u2019)]}")
	return bool(stripped) and stripped[-1:] in ".!?"


def word_count(text: str) -> int:
	return len(re.findall(r"\b\w+\b", text))


def render_preview_text(text: str) -> str:
	return text.replace("\r", "<carriage return>").replace("\n", "<newline>").replace("\t", "<tab>")
