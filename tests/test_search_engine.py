import tempfile
import zipfile
from pathlib import Path

from scripts.package_addon import build_package
from addon.globalPlugins.folderTextFinder.search_engine import (
	SearchOptions,
	SearchResult,
	find_matches,
	line_column_for_offset,
	literal_spans,
	preview_for_span,
)
from addon.globalPlugins.folderTextFinder import format_result_for_list, normalize_search_folder, path_from_shell_location_url, render_invisible_text
from addon.globalPlugins.folderTextFinder.text_extractors import ExtractedText


def test_literal_search_matches_punctuation_and_partial_words():
	text = "alpha C:\\Users\\Tara\\file-name.txt omega"
	results = list(find_matches(Path("example.txt"), ExtractedText(text), SearchOptions(query="file-name.txt")))
	assert len(results) == 1
	assert results[0].column == 21


def test_literal_search_matches_repeated_spaces():
	text = "foo   bar\nfoo bar"
	results = list(find_matches(Path("example.txt"), ExtractedText(text), SearchOptions(query="foo   bar")))
	assert len(results) == 1
	assert results[0].line == 1


def test_literal_search_matches_tabs_and_newlines():
	text = "first\tsecond\nthird"
	results = list(find_matches(Path("example.txt"), ExtractedText(text), SearchOptions(query="\tsecond\nthird")))
	assert len(results) == 1
	assert results[0].line == 1
	assert results[0].column == 6


def test_whole_word_search_does_not_match_inside_words():
	text = "cat scatter cat"
	results = list(find_matches(Path("example.txt"), ExtractedText(text), SearchOptions(query="cat", whole_word=True)))
	assert len(results) == 2
	assert [result.column for result in results] == [1, 13]


def test_case_insensitive_search_matches_uppercase_text():
	text = "MIXED mixed"
	results = list(find_matches(Path("example.txt"), ExtractedText(text), SearchOptions(query="mixed")))
	assert len(results) == 2


def test_line_column_for_offset():
	assert line_column_for_offset("one\ntwo\nthree", 8) == (3, 1)


def test_literal_spans_do_not_overlap():
	assert list(literal_spans("aaaa", "aa")) == [(0, 2), (2, 4)]


def test_path_from_shell_location_url_decodes_file_url():
	assert path_from_shell_location_url("file:///C:/Users/Tara/Documents/My%20Folder") == "C:\\Users\\Tara\\Documents\\My Folder"


def test_render_invisible_text_makes_whitespace_readable():
	assert render_invisible_text("one  two\tthree\nfour") == "one<space><space>two<tab>three<newline>\nfour"


def test_package_contains_manifest_plugin_and_html_guide():
	package = build_package()
	with zipfile.ZipFile(package) as archive:
		names = set(archive.namelist())
	assert "manifest.ini" in names
	assert "globalPlugins/folderTextFinder/__init__.py" in names
	assert "doc/en/readme.html" in names


def test_normalize_search_folder_accepts_folder():
	with tempfile.TemporaryDirectory() as temp_dir:
		folder = Path(temp_dir) / "books"
		folder.mkdir()
		assert normalize_search_folder(str(folder)) == str(folder)


def test_normalize_search_folder_uses_parent_for_file():
	with tempfile.TemporaryDirectory() as temp_dir:
		folder = Path(temp_dir) / "books"
		folder.mkdir()
		book = folder / "chapter.txt"
		book.write_text("hello", encoding="utf-8")
		assert normalize_search_folder(str(book)) == str(folder)


def test_format_result_for_list_contains_location_and_preview():
	result = SearchResult(path=Path("book.txt"), line=3, column=5, preview="matching text")
	formatted = format_result_for_list(result)
	assert "book.txt" in formatted
	assert "Line 3, Column 5" in formatted
	assert "matching text" in formatted


def test_exact_whole_word_search_does_not_match_apostrophe_suffix():
	text = "sister sister's sisterhood"
	results = list(find_matches(Path("example.txt"), ExtractedText(text), SearchOptions(query="sister", whole_word=True)))
	assert len(results) == 1
	assert results[0].column == 1


def test_exact_whole_word_search_does_not_match_curly_apostrophe_suffix():
	text = "sister sister\u2019s sisterhood"
	results = list(find_matches(Path("example.txt"), ExtractedText(text), SearchOptions(query="sister", whole_word=True)))
	assert len(results) == 1
	assert results[0].column == 1


def test_preview_uses_full_sentence_for_prose():
	text = "Before. My sister opened the old wooden door slowly. After."
	start = text.index("sister")
	preview = preview_for_span(text, start, start + len("sister"))
	assert preview == "My sister opened the old wooden door slowly."


def test_preview_adds_next_sentence_when_sentence_is_short():
	text = "Before. Sister smiled. Then she waved from the doorway. After."
	start = text.index("Sister")
	preview = preview_for_span(text, start, start + len("Sister"))
	assert preview == "Sister smiled. Then she waved from the doorway."


def test_preview_falls_back_for_code_like_text_without_sentence_punctuation():
	text = "alpha sister beta gamma"
	start = text.index("sister")
	preview = preview_for_span(text, start, start + len("sister"))
	assert "alpha sister beta" in preview

def test_preview_stops_at_question_mark_inside_closing_quote():
	text = 'Before. "Where is my sister?" Mother asked. After.'
	start = text.index("sister")
	preview = preview_for_span(text, start, start + len("sister"))
	assert preview == '"Where is my sister?"'


def test_preview_stops_at_exclamation_mark_inside_closing_quote():
	text = 'Before. "Run, sister!" Mother shouted. After.'
	start = text.index("sister")
	preview = preview_for_span(text, start, start + len("sister"))
	assert preview == '"Run, sister!"'

def test_search_result_keeps_exact_match_offsets():
	text = "alpha sister beta"
	result = list(find_matches(Path("example.txt"), ExtractedText(text), SearchOptions(query="sister")))[0]
	assert result.start == text.index("sister")
	assert result.end == result.start + len("sister")

def test_docx_result_location_uses_open_result_label():
	text = "First paragraph\nSecond paragraph with cat"
	result = list(find_matches(Path("book.docx"), ExtractedText(text), SearchOptions(query="cat")))[0]
	assert result.format_location() == "Exact position in Open Result"


def test_text_result_location_uses_line_label():
	text = "First line\nSecond line with cat"
	result = list(find_matches(Path("book.txt"), ExtractedText(text), SearchOptions(query="cat")))[0]
	assert result.format_location() == "Line 2, Column 18"
