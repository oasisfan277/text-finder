import tempfile
import zipfile
from pathlib import Path

from scripts.package_addon import build_package
from addon.globalPlugins.textFinder import text_extractors as text_extractors_module
from addon.globalPlugins.textFinder.search_engine import (
	SearchOptions,
	SearchResult,
	SearchStatistics,
	Searcher,
	find_matches,
	line_column_for_offset,
	literal_spans,
	preview_for_span,
)
from addon.globalPlugins.textFinder import (
	WORD_LOCATION_BATCH_SIZE,
	batched_items,
	file_type_choice_label,
	file_type_is_selected,
	format_result_for_list,
	get_active_file_patterns,
	get_open_word_visual_locations,
	get_word_active_document_path,
	OPEN_WORD_LOCATION_SCRIPT,
	word_file_name_from_object_name,
	open_word_document_editable,
	open_word_document_read_only,
	ordered_supported_file_types,
	normalize_search_folder,
	normalize_search_target,
	parse_extension_list,
	path_from_shell_location_url,
	render_invisible_text,
)
from addon.globalPlugins.textFinder.text_extractors import (
	ExtractedText,
	all_supported_extensions,
	extract_docx,
	extract_text,
	powershell_executables,
	DOCX_POWERSHELL_READER,
)




class _FakeWordDocument:
	def __init__(self, path):
		self.FullName = str(path)


class _FakeWord:
	def __init__(self, path):
		self.ActiveDocument = _FakeWordDocument(path)


class _NoProtectedViewWindows:
	Count = 0






def test_open_word_document_read_only_uses_read_only_flags():
	class FakeDocuments:
		def __init__(self):
			self.calls = []

		def Open(self, *args):
			self.calls.append(args)
			return "document"

	class FakeWord:
		def __init__(self):
			self.Documents = FakeDocuments()

	word = FakeWord()
	assert open_word_document_read_only(word, Path("book.docx")) == "document"
	assert word.Documents.calls == [("book.docx", False, True, False)]


def test_open_word_document_editable_uses_editable_flags():
	class FakeDocuments:
		def __init__(self):
			self.calls = []

		def Open(self, *args):
			self.calls.append(args)
			return "document"

	class FakeWord:
		def __init__(self):
			self.Documents = FakeDocuments()

	word = FakeWord()
	assert open_word_document_editable(word, Path("book.docx")) == "document"
	assert word.Documents.calls == [("book.docx", False, False, True)]


def test_open_word_location_script_uses_running_word_document():
	assert "GetActiveObject('Word.Application')" in OPEN_WORD_LOCATION_SCRIPT
	assert "$word.Documents.Count" in OPEN_WORD_LOCATION_SCRIPT
	assert "selectResult" in OPEN_WORD_LOCATION_SCRIPT
	assert "$payload.fullName" in OPEN_WORD_LOCATION_SCRIPT
	assert "AppActivate" in OPEN_WORD_LOCATION_SCRIPT


def test_word_location_batch_size_is_ten_results():
	assert WORD_LOCATION_BATCH_SIZE == 10
	assert list(batched_items(list(range(25)), WORD_LOCATION_BATCH_SIZE)) == [
		list(range(10)),
		list(range(10, 20)),
		list(range(20, 25)),
	]


def test_selected_file_types_are_ordered_first_when_search_all_is_off():
	ordered = ordered_supported_file_types(False, {".docx", ".txt"})
	assert ordered[0][0] == "Plain text and logs (.txt, .log)"
	assert ordered[1][0] == "Word documents (.docx)"
	assert ordered_supported_file_types(True, {".docx"})[0][0] == "Plain text and logs (.txt, .log)"


def test_pdf_is_not_a_default_supported_type():
	extensions = all_supported_extensions()
	assert ".pdf" not in extensions


def test_word_file_name_from_word_window_title():
	assert word_file_name_from_object_name("Grimm fairytales for bookclub.docx - Word") == "Grimm fairytales for bookclub.docx"


def test_word_file_name_from_document_pane_name():
	assert word_file_name_from_object_name("Grimm fairytales for bookclub.docx") == "Grimm fairytales for bookclub.docx"
def test_word_active_document_path_uses_active_document():
	with tempfile.TemporaryDirectory() as temp_dir:
		path = Path(temp_dir) / "book.docx"
		path.write_text("placeholder", encoding="utf-8")
		assert get_word_active_document_path(_FakeWord(path)) == str(path)


def test_word_active_document_path_returns_none_for_unsaved_document():
	class UnsavedWord:
		ProtectedViewWindows = _NoProtectedViewWindows()
		@property
		def ActiveDocument(self):
			raise RuntimeError("unsaved")

	assert get_word_active_document_path(UnsavedWord()) is None
def test_file_type_choice_label_includes_selection_state():
	assert file_type_choice_label("Word documents (.docx)", True) == "Selected: Word documents (.docx)"
	assert file_type_choice_label("Plain text and logs (.txt, .log)", False) == "Not selected: Plain text and logs (.txt, .log)"


def test_file_type_selection_helper_clears_when_search_all_is_off():
	assert file_type_is_selected(True, set(), (".txt",)) is True
	assert file_type_is_selected(False, set(), (".txt",)) is False
	assert file_type_is_selected(False, {".txt"}, (".txt", ".log")) is True
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
	assert "globalPlugins/textFinder/__init__.py" in names
	assert "doc/en/readme.html" in names



def test_normalize_search_target_accepts_file():
	with tempfile.TemporaryDirectory() as temp_dir:
		path = Path(temp_dir) / "chapter.txt"
		path.write_text("hello", encoding="utf-8")
		assert normalize_search_target(str(path)) == str(path)

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











def test_docx_powershell_reader_uses_shared_file_access():
	assert "FileShare" in DOCX_POWERSHELL_READER
	assert "ReadWrite" in DOCX_POWERSHELL_READER
	assert "Delete" in DOCX_POWERSHELL_READER
def test_powershell_executables_prefers_full_windows_path():
	executables = powershell_executables()
	assert executables[0].lower().endswith("windowspowershell\\v1.0\\powershell.exe")
	assert executables[-1] == "powershell.exe"
def test_docx_permission_error_uses_locked_file_fallback():
	original_zip = text_extractors_module.extract_docx_from_zip
	original_locked = text_extractors_module.extract_docx_from_locked_file
	calls = []

	def fake_zip(path):
		raise PermissionError("locked")

	def fake_locked(path):
		calls.append(path)
		return ExtractedText("cat")

	text_extractors_module.extract_docx_from_zip = fake_zip
	text_extractors_module.extract_docx_from_locked_file = fake_locked
	try:
		path = Path("book.docx")
		assert extract_docx(path).text == "cat"
		assert calls == [path]
	finally:
		text_extractors_module.extract_docx_from_zip = original_zip
		text_extractors_module.extract_docx_from_locked_file = original_locked
def test_searcher_accepts_string_file_target():
	with tempfile.TemporaryDirectory() as temp_dir:
		path = Path(temp_dir) / "chapter.txt"
		path.write_text("cat", encoding="utf-8")
		results, statistics = Searcher(str(path), SearchOptions(query="cat", file_patterns=("*.docx",))).search()
		assert len(results) == 1
		assert statistics.supported_files_searched == 1
def test_searcher_searches_single_file_even_when_filter_excludes_it():
	with tempfile.TemporaryDirectory() as temp_dir:
		path = Path(temp_dir) / "chapter.txt"
		path.write_text("needle", encoding="utf-8")
		results, statistics = Searcher(path, SearchOptions(query="needle", file_patterns=("*.docx",))).search()
		assert len(results) == 1
		assert results[0].path == path
		assert statistics.supported_files_searched == 1


def test_searcher_searches_targeted_unknown_extension_text_file():
	with tempfile.TemporaryDirectory() as temp_dir:
		path = Path(temp_dir) / "notes.readmefile"
		path.write_text("needle in plain text", encoding="utf-8")
		results, statistics = Searcher(path, SearchOptions(query="needle", file_patterns=("*.docx",))).search()
		assert len(results) == 1
		assert results[0].path == path
		assert statistics.supported_files_searched == 1


def test_searcher_skips_targeted_unknown_extension_binary_file():
	with tempfile.TemporaryDirectory() as temp_dir:
		path = Path(temp_dir) / "sound.musicfile"
		path.write_bytes(b"\x00\x01\x02\x03not text")
		results, statistics = Searcher(path, SearchOptions(query="text", file_patterns=("*.txt",))).search()
		assert results == []
		assert statistics.supported_files_searched == 0
		assert len(statistics.unsupported_files) == 1

def test_format_result_for_list_contains_location_and_preview():
	result = SearchResult(path=Path("book.txt"), line=3, column=5, preview="matching text")
	formatted = format_result_for_list(result)
	assert "book.txt" in formatted
	assert "Line 3, Column 5" in formatted
	assert "matching text" in formatted


def test_format_result_for_list_omits_full_path_by_default():
	result = SearchResult(path=Path("C:/library/reading/book.txt"), line=1, column=1, preview="x")
	formatted = format_result_for_list(result)
	assert "book.txt" in formatted
	assert "library" not in formatted
	assert "reading" not in formatted


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

def test_docx_result_starts_pending_word_location():
	text = "First paragraph\nSecond paragraph with cat"
	result = list(find_matches(Path("book.docx"), ExtractedText(text), SearchOptions(query="cat")))[0]
	assert result.word_pending is True
	assert result.format_location() == "Word location loading"


def test_docx_result_falls_back_to_open_result_label():
	result = SearchResult(path=Path("book.docx"), line=1, column=1, preview="match", location_unit="Open Result", word_pending=False)
	assert result.format_location() == "Exact position in Open Result"


def test_text_result_location_uses_line_label():
	text = "First line\nSecond line with cat"
	result = list(find_matches(Path("book.txt"), ExtractedText(text), SearchOptions(query="cat")))[0]
	assert result.format_location() == "Line 2, Column 18"


def test_single_file_statistics_omit_folder_counts():
	with tempfile.TemporaryDirectory() as temp_dir:
		path = Path(temp_dir) / "book.docx"
		path.write_text("placeholder", encoding="utf-8")
		statistics = SearchStatistics(path, SearchOptions(query="cat"), matches_found=3)
		report = statistics.to_report()
		assert statistics.summary_message() == "Search complete. 3 matches found in this file."
		assert "Search file:" in report
		assert "Include subfolders" not in report
		assert "Supported files searched" not in report
		assert "Files containing matches" not in report


def test_single_file_statistics_report_unreadable_file():
	with tempfile.TemporaryDirectory() as temp_dir:
		path = Path(temp_dir) / "book.docx"
		path.write_text("placeholder", encoding="utf-8")
		statistics = SearchStatistics(path, SearchOptions(query="cat"))
		statistics.unreadable_files.append((path, "Permission denied"))
		assert statistics.summary_message() == "Search complete. This file could not be read."


def test_word_visual_line_location_omits_column():
	result = SearchResult(path=Path("book.docx"), line=12, column=0, preview="match", page=3, location_unit="Visual line")
	assert result.format_location() == "Page 3, visual line 12"


def _write_zip(path: Path, members: dict[str, str]) -> None:
	with zipfile.ZipFile(path, "w") as archive:
		for name, content in members.items():
			archive.writestr(name, content)


def test_extract_xlsx_reads_shared_strings():
	with tempfile.TemporaryDirectory() as temp_dir:
		path = Path(temp_dir) / "book.xlsx"
		_write_zip(path, {
			"xl/sharedStrings.xml": (
				'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
				'<si><t>Quarterly revenue</t></si><si><t>hidden keyword</t></si></sst>'
			),
		})
		extracted = extract_text(path)
		assert "Quarterly revenue" in extracted.text
		assert "hidden keyword" in extracted.text


def test_extract_pptx_reads_slide_text_in_order():
	with tempfile.TemporaryDirectory() as temp_dir:
		path = Path(temp_dir) / "deck.pptx"
		_write_zip(path, {
			"ppt/slides/slide2.xml": '<p:sld xmlns:p="p" xmlns:a="a"><a:t>Second slide</a:t></p:sld>',
			"ppt/slides/slide1.xml": '<p:sld xmlns:p="p" xmlns:a="a"><a:t>First</a:t><a:t>slide</a:t></p:sld>',
		})
		extracted = extract_text(path)
		assert extracted.text == "First slide\nSecond slide"


def test_xlsx_and_pptx_are_supported_types():
	extensions = all_supported_extensions()
	assert ".xlsx" in extensions
	assert ".pptx" in extensions


def test_parse_extension_list_normalizes_entries():
	assert parse_extension_list("txt; .docx ;RTF") == [".txt", ".docx", ".rtf"]
	assert parse_extension_list("") == []


def test_active_file_patterns_default_to_all_supported_types():
	patterns = get_active_file_patterns()
	assert "*.xlsx" in patterns
	assert "*.pptx" in patterns
	assert "*.docx" in patterns
