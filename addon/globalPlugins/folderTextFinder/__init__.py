import os
import subprocess
import threading
import traceback
from dataclasses import replace
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
	import config
	import globalPluginHandler
	import gui
	import scriptHandler
	import ui
	import wx
	from gui import guiHelper
	from gui.settingsDialogs import NVDASettingsDialog, SettingsPanel
except ModuleNotFoundError:
	class _BaseGlobalPlugin:
		pass

	class _GlobalPluginHandler:
		GlobalPlugin = _BaseGlobalPlugin

	class _ScriptHandler:
		@staticmethod
		def script(**kwargs):
			def decorator(func):
				return func
			return decorator

	class _UI:
		@staticmethod
		def message(text):
			return None

	class _SettingsPanel:
		pass

	class _Dialog:
		pass

	class _WX:
		Dialog = _Dialog

	config = None
	globalPluginHandler = _GlobalPluginHandler()
	gui = None
	guiHelper = None
	NVDASettingsDialog = None
	SettingsPanel = _SettingsPanel
	scriptHandler = _ScriptHandler()
	ui = _UI()
	wx = _WX()

from .search_engine import SearchOptions, Searcher
from .text_extractors import TextExtractionError, extract_text


try:
	_
except NameError:
	_ = lambda text: text


CONFIG_SECTION = "folderTextFinder"
DEFAULT_FILE_FILTERS = "*.txt;*.md;*.log;*.ini;*.csv;*.json;*.xml;*.html;*.htm;*.css;*.js;*.py;*.docx;*.rtf;*.odt;*.pdf"


def _initialize_config():
	if config is None:
		return
	config.conf.spec[CONFIG_SECTION] = {
		"allowDirectTabsAndLineBreaks": "boolean(default=False)",
		"announceInvisibleCharacters": "boolean(default=False)",
		"reportPageNumbers": "boolean(default=True)",
	}


def get_setting(name):
	defaults = {
		"allowDirectTabsAndLineBreaks": False,
		"announceInvisibleCharacters": False,
		"reportPageNumbers": True,
	}
	try:
		return config.conf[CONFIG_SECTION][name]
	except Exception:
		return defaults[name]


_initialize_config()


def log_info(message, *args):
	try:
		import logHandler

		logHandler.log.info(message, *args)
	except Exception:
		pass


def log_exception(message):
	try:
		import logHandler

		logHandler.log.error("%s\n%s", message, traceback.format_exc())
	except Exception:
		pass


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = _("Folder Text Finder")

	def __init__(self):
		super().__init__()
		self._dialog = None
		if NVDASettingsDialog and FolderTextFinderSettingsPanel not in NVDASettingsDialog.categoryClasses:
			NVDASettingsDialog.categoryClasses.append(FolderTextFinderSettingsPanel)

	def terminate(self):
		if NVDASettingsDialog and FolderTextFinderSettingsPanel in NVDASettingsDialog.categoryClasses:
			NVDASettingsDialog.categoryClasses.remove(FolderTextFinderSettingsPanel)
		super().terminate()

	@scriptHandler.script(
		description=_("Search files containing text in the current File Explorer folder"),
		gesture="kb:NVDA+alt+f",
	)
	def script_openFolderTextFinder(self, gesture):
		ui.message(_("Folder Text Finder starting."))
		log_info("Folder Text Finder command started.")
		try:
			folder = get_current_explorer_folder()
		except Exception:
			log_exception("Folder Text Finder folder detection crashed.")
			ui.message(_("Folder Text Finder could not detect the folder."))
			return
		if not folder:
			log_folder_detection_diagnostics()
			ui.message(_("Open a folder or focus a file before using Folder Text Finder."))
			return
		log_info("Folder Text Finder opening dialog for folder: %s", folder)
		wx.CallAfter(self._show_dialog, folder)

	def _show_dialog(self, folder):
		if self._dialog:
			try:
				self._dialog.Destroy()
			except Exception as exc:
				pass
		self._dialog = FolderTextFinderDialog(gui.mainFrame, folder)
		self._dialog.Bind(wx.EVT_WINDOW_DESTROY, self._on_dialog_destroy)
		self._dialog.present()

	def _on_dialog_destroy(self, evt):
		if evt.GetEventObject() is self._dialog:
			self._dialog = None
		evt.Skip()


class FolderTextFinderSettingsPanel(SettingsPanel):
	title = _("Folder Text Finder")

	def makeSettings(self, settingsSizer):
		settingsSizerHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self.allowDirectTabsAndLineBreaksCtrl = settingsSizerHelper.addItem(
			wx.CheckBox(self, label=_("Allow direct entry of tabs and line breaks in the search field"))
		)
		self.allowDirectTabsAndLineBreaksCtrl.SetValue(get_setting("allowDirectTabsAndLineBreaks"))
		self.announceInvisibleCharactersCtrl = settingsSizerHelper.addItem(
			wx.CheckBox(self, label=_("Announce invisible characters while typing"))
		)
		self.announceInvisibleCharactersCtrl.SetValue(get_setting("announceInvisibleCharacters"))
		self.reportPageNumbersCtrl = settingsSizerHelper.addItem(
			wx.CheckBox(self, label=_("Report page numbers when available"))
		)
		self.reportPageNumbersCtrl.SetValue(get_setting("reportPageNumbers"))

	def onSave(self):
		config.conf[CONFIG_SECTION]["allowDirectTabsAndLineBreaks"] = self.allowDirectTabsAndLineBreaksCtrl.GetValue()
		config.conf[CONFIG_SECTION]["announceInvisibleCharacters"] = self.announceInvisibleCharactersCtrl.GetValue()
		config.conf[CONFIG_SECTION]["reportPageNumbers"] = self.reportPageNumbersCtrl.GetValue()


def get_current_explorer_folder():
	folder = get_folder_from_focused_object()
	if folder:
		return folder
	return get_foreground_explorer_folder_from_shell()


def get_folder_from_focused_object():
	try:
		import api

		objects = [api.getFocusObject(), api.getForegroundObject()]
		seen = set()
		for obj in objects:
			while obj and id(obj) not in seen:
				seen.add(id(obj))
				for attr in ("location", "value", "name"):
					folder = normalize_search_folder(getattr(obj, attr, None))
					if folder:
						return folder
				obj = getattr(obj, "parent", None)
	except Exception:
		pass
	return None


def get_foreground_explorer_folder_from_shell():
	try:
		import ctypes

		GA_ROOT = 2
		foreground_hwnd = ctypes.windll.user32.GetForegroundWindow()
		foreground_root = ctypes.windll.user32.GetAncestor(foreground_hwnd, GA_ROOT) or foreground_hwnd
		shell = get_shell_application()
		candidate_folders = []
		selected_folders = []
		for window in shell.Windows():
			try:
				selected_folder = get_selected_folder_from_shell_window(window)
				folder = selected_folder or normalize_search_folder(window.LocationURL)
				if not folder:
					continue
				candidate_folders.append(folder)
				if selected_folder:
					selected_folders.append(selected_folder)
				if int(window.HWND) == foreground_root:
					return folder
			except Exception:
				last_error = str(exc)
				continue
		if len(selected_folders) == 1:
			return selected_folders[0]
		if len(candidate_folders) == 1:
			return candidate_folders[0]
	except Exception:
		return None
	return None


def get_selected_folder_from_shell_window(window):
	try:
		selected_items = window.Document.SelectedItems()
		if selected_items.Count != 1:
			return None
		return normalize_search_folder(selected_items.Item(0).Path)
	except Exception:
		return None


def get_shell_application():
	try:
		import comtypes.client

		return comtypes.client.CreateObject("Shell.Application", dynamic=True)
	except Exception:
		try:
			import win32com.client

			return win32com.client.Dispatch("Shell.Application")
		except Exception:
			raise


def path_from_shell_location_url(location_url):
	if not location_url:
		return None
	if location_url.startswith("file:///"):
		parsed = urlparse(location_url)
		path = unquote(parsed.path)
		if path.startswith("/") and len(path) > 2 and path[2] == ":":
			path = path[1:]
		return path.replace("/", "\\")
	return location_url


def normalize_search_folder(candidate):
	if not candidate:
		return None
	path = path_from_shell_location_url(str(candidate).strip().strip('"'))
	path = os.path.expandvars(path)
	if os.path.isdir(path):
		return path
	if os.path.isfile(path):
		return os.path.dirname(path)
	return None



def log_folder_detection_diagnostics():
	try:
		import api
		import logHandler

		log = logHandler.log
		log.info("Folder Text Finder folder detection failed. Starting diagnostics.")
		for label, obj in (("focus", api.getFocusObject()), ("foreground", api.getForegroundObject()), ("navigator", api.getNavigatorObject())):
			log.info("Folder Text Finder %s object chain:", label)
			seen = set()
			depth = 0
			while obj and id(obj) not in seen and depth < 8:
				seen.add(id(obj))
				log.info(
					"  depth=%s class=%r role=%r name=%r value=%r location=%r appModule=%r",
					depth,
					getattr(obj, "windowClassName", None),
					getattr(obj, "role", None),
					getattr(obj, "name", None),
					getattr(obj, "value", None),
					getattr(obj, "location", None),
					getattr(getattr(obj, "appModule", None), "appName", None),
				)
				obj = getattr(obj, "parent", None)
				depth += 1
		log_shell_window_diagnostics(log)
	except Exception:
		try:
			import logHandler
			logHandler.log.error("Folder Text Finder diagnostics failed:\n%s", traceback.format_exc())
		except Exception:
			pass


def log_shell_window_diagnostics(log):
	try:
		import ctypes

		GA_ROOT = 2
		foreground_hwnd = ctypes.windll.user32.GetForegroundWindow()
		foreground_root = ctypes.windll.user32.GetAncestor(foreground_hwnd, GA_ROOT) or foreground_hwnd
		log.info("Folder Text Finder foreground hwnd=%r root=%r", foreground_hwnd, foreground_root)
		shell = get_shell_application()
		for index, window in enumerate(shell.Windows()):
			try:
				log.info("Folder Text Finder shell window %s hwnd=%r url=%r normalized=%r", index, int(window.HWND), window.LocationURL, normalize_search_folder(window.LocationURL))
				selected_items = window.Document.SelectedItems()
				log.info("Folder Text Finder shell window %s selected count=%r", index, selected_items.Count)
				for item_index in range(selected_items.Count):
					item = selected_items.Item(item_index)
					log.info("Folder Text Finder selected item %s path=%r normalized=%r", item_index, item.Path, normalize_search_folder(item.Path))
			except Exception:
				log.info("Folder Text Finder shell window %s diagnostics failed:\n%s", index, traceback.format_exc())
	except Exception:
		log.info("Folder Text Finder shell diagnostics failed:\n%s", traceback.format_exc())

class FolderTextFinderDialog(wx.Dialog):
	def __init__(self, parent, folder):
		super().__init__(parent, title=_("Folder Text Finder"))
		self.folder = folder
		self.results = []
		self.statistics = None
		self._lastQueryValue = ""
		self._build()
		self.CentreOnScreen()

	def present(self):
		self.Show()
		self.Raise()
		self.SetFocus()
		self.queryCtrl.SetFocus()
		ui.message(_("Folder Text Finder opened. Search folder: {folder}").format(folder=self.folder))
		log_info("Folder Text Finder dialog presented for folder: %s", self.folder)

	def _build(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(wx.StaticText(self, label=_("Folder: {folder}").format(folder=self.folder)), 0, wx.ALL, 8)

		mainSizer.Add(wx.StaticText(self, label=_("&Search text:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.queryCtrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER)
		mainSizer.Add(self.queryCtrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
		mainSizer.Add(wx.StaticText(self, label=_("Search text &preview:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.previewCtrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
		mainSizer.Add(self.previewCtrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

		searchModeSizer = wx.StaticBoxSizer(wx.VERTICAL, self, _("Search mode"))
		self.exactFragmentCtrl = wx.RadioButton(self, label=_("Exact &fragment"), style=wx.RB_GROUP)
		self.exactWholeWordCtrl = wx.RadioButton(self, label=_("Exact &whole word"))
		self.exactFragmentCtrl.SetValue(True)
		searchModeSizer.Add(self.exactFragmentCtrl, 0, wx.ALL, 4)
		searchModeSizer.Add(self.exactWholeWordCtrl, 0, wx.ALL, 4)
		self.caseCtrl = wx.CheckBox(self, label=_("&Case sensitive"))
		self.subfoldersCtrl = wx.CheckBox(self, label=_("Include &subfolders"))
		self.reportPagesCtrl = wx.CheckBox(self, label=_("Report &page numbers when available"))
		self.reportPagesCtrl.SetValue(get_setting("reportPageNumbers"))
		self.filterCtrl = wx.TextCtrl(self, value=DEFAULT_FILE_FILTERS)

		mainSizer.Add(searchModeSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)
		mainSizer.Add(self.caseCtrl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		mainSizer.Add(self.subfoldersCtrl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		mainSizer.Add(self.reportPagesCtrl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		mainSizer.Add(wx.StaticText(self, label=_("File name &filters:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		mainSizer.Add(self.filterCtrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

		mainSizer.Add(wx.StaticText(self, label=_("Search &results:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.resultsCtrl = wx.ListBox(self, style=wx.LB_SINGLE)
		mainSizer.Add(self.resultsCtrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

		buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.searchButton = wx.Button(self, label=_("&Search"))
		self.openFileButton = wx.Button(self, label=_("Open &File"))
		self.openButton = wx.Button(self, label=_("&Open Result"))
		self.statsButton = wx.Button(self, label=_("Search &Statistics"))
		self.closeButton = wx.Button(self, wx.ID_CLOSE)
		for button in (self.searchButton, self.openFileButton, self.openButton, self.statsButton, self.closeButton):
			buttonSizer.Add(button, 0, wx.ALL, 4)
		mainSizer.Add(buttonSizer, 0, wx.ALIGN_RIGHT | wx.ALL, 4)

		self.SetSizer(mainSizer)
		self.SetSize((900, 650))

		self.searchButton.Bind(wx.EVT_BUTTON, self.on_search)
		self.openFileButton.Bind(wx.EVT_BUTTON, self.on_open_file_from_result)
		self.openButton.Bind(wx.EVT_BUTTON, self.on_open_result)
		self.statsButton.Bind(wx.EVT_BUTTON, self.on_statistics)
		self.closeButton.Bind(wx.EVT_BUTTON, lambda evt: self.Destroy())
		self.queryCtrl.Bind(wx.EVT_CHAR_HOOK, self.on_query_char_hook)
		self.queryCtrl.Bind(wx.EVT_TEXT, self.on_query_text)
		self.resultsCtrl.Bind(wx.EVT_LISTBOX_DCLICK, self.on_open_result)
		self.resultsCtrl.Bind(wx.EVT_CHAR_HOOK, self.on_results_char_hook)

	def on_search(self, evt):
		query = self.queryCtrl.GetValue()
		if not query:
			ui.message(_("Enter text to search for."))
			return
		self.searchButton.Disable()
		self.resultsCtrl.Clear()
		ui.message(_("Searching."))
		options = SearchOptions(
			query=query,
			whole_word=self.exactWholeWordCtrl.GetValue(),
			case_sensitive=self.caseCtrl.GetValue(),
			include_subfolders=self.subfoldersCtrl.GetValue(),
			file_patterns=tuple(pattern.strip() for pattern in self.filterCtrl.GetValue().split(";") if pattern.strip()),
			report_page_numbers=self.reportPagesCtrl.GetValue(),
		)
		thread = threading.Thread(target=self._run_search, args=(options,), daemon=True)
		thread.start()

	def on_query_char_hook(self, evt):
		key_code = evt.GetKeyCode()
		if get_setting("allowDirectTabsAndLineBreaks") and key_code in (wx.WXK_TAB, wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			character = "\t" if key_code == wx.WXK_TAB else "\n"
			self.queryCtrl.WriteText(character)
			if get_setting("announceInvisibleCharacters"):
				ui.message(_("tab") if character == "\t" else _("newline"))
			return
		if get_setting("announceInvisibleCharacters") and key_code == wx.WXK_SPACE:
			wx.CallAfter(self.announce_space_run)
		evt.Skip()

	def on_query_text(self, evt):
		value = self.queryCtrl.GetValue()
		self.previewCtrl.SetValue(render_invisible_text(value))
		self._lastQueryValue = value
		evt.Skip()

	def announce_space_run(self):
		value = self.queryCtrl.GetValue()
		insertion_point = self.queryCtrl.GetInsertionPoint()
		run = 0
		index = insertion_point - 1
		while index >= 0 and value[index] == " ":
			run += 1
			index -= 1
		if run <= 1:
			ui.message(_("space"))
		else:
			ui.message(_("{count} spaces").format(count=run))

	def _run_search(self, options):
		searcher = Searcher(Path(self.folder), options)
		results, statistics = searcher.search()
		wx.CallAfter(self._finish_search, results, statistics)

	def _finish_search(self, results, statistics):
		self.results = results
		self.statistics = statistics
		self.refresh_results_list()
		self.searchButton.Enable()
		if results:
			self.resultsCtrl.SetSelection(0)
			self.resultsCtrl.SetFocus()
		ui.message(statistics.summary_message())

	def refresh_results_list(self):
		selection = self.resultsCtrl.GetSelection()
		self.resultsCtrl.Clear()
		for result in self.results:
			self.resultsCtrl.Append(format_result_for_list(result))
		if self.results:
			if selection == wx.NOT_FOUND or selection < 0 or selection >= len(self.results):
				selection = 0
			self.resultsCtrl.SetSelection(selection)

	def on_results_char_hook(self, evt):
		key_code = evt.GetKeyCode()
		if key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			self.open_selected_result()
			return
		evt.Skip()

	def on_open_result(self, evt):
		self.open_selected_result()

	def open_selected_result(self):
		result = self.get_selected_result()
		if result is None:
			return
		try:
			extracted = extract_text(result.path)
		except TextExtractionError as exc:
			ui.message(_("Could not open result text: {reason}").format(reason=exc.message))
			return
		except Exception:
			log_exception("Folder Text Finder could not open result text.")
			ui.message(_("Could not open result text."))
			return
		ResultLocationDialog(self, result, extracted.text).Show()

	def on_open_file_from_result(self, evt):
		result = self.get_selected_result()
		if result is None:
			return
		updated_result = open_result_file(result)
		if updated_result is not None and updated_result != result:
			index = self.resultsCtrl.GetSelection()
			self.results[index] = updated_result
			self.refresh_results_list()

	def get_selected_result(self):
		index = self.resultsCtrl.GetSelection()
		if index == wx.NOT_FOUND or index < 0 or index >= len(self.results):
			ui.message(_("Select a result first."))
			return None
		return self.results[index]

	def on_statistics(self, evt):
		if not self.statistics:
			ui.message(_("No search statistics are available yet."))
			return
		StatisticsDialog(self, self.statistics.to_report()).Show()

class ResultLocationDialog(wx.Dialog):
	def __init__(self, parent, result, text):
		super().__init__(parent, title=_("Search Result"))
		self.result = result
		self.text = text
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(wx.StaticText(self, label=_("File: {path}").format(path=result.path)), 0, wx.ALL, 8)
		self.locationLabel = wx.StaticText(self, label=_("Location: {location}").format(location=result.format_location()))
		sizer.Add(self.locationLabel, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
		self.textCtrl = wx.TextCtrl(self, value=text, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
		sizer.Add(self.textCtrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
		buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
		openFileButton = wx.Button(self, label=_("Open &File"))
		closeButton = wx.Button(self, wx.ID_CLOSE)
		buttonSizer.Add(openFileButton, 0, wx.ALL, 4)
		buttonSizer.Add(closeButton, 0, wx.ALL, 4)
		sizer.Add(buttonSizer, 0, wx.ALIGN_RIGHT | wx.ALL, 4)
		self.SetSizer(sizer)
		self.SetSize((900, 650))
		openFileButton.Bind(wx.EVT_BUTTON, self.on_open_file)
		closeButton.Bind(wx.EVT_BUTTON, lambda evt: self.Destroy())
		wx.CallAfter(self.focus_match)

	def focus_match(self):
		start = max(0, min(self.result.start, len(self.text)))
		end = max(start, min(self.result.end, len(self.text)))
		self.Raise()
		self.textCtrl.SetFocus()
		self.textCtrl.SetInsertionPoint(start)
		self.textCtrl.SetSelection(start, end)
		if self.result.location_unit == "Open Result":
			ui.message(_("Result opened at the exact match."))
		else:
			ui.message(_("Result opened at {location}.").format(location=self.result.format_location()))

	def on_open_file(self, evt):
		updated_result = open_result_file(self.result, self.text)
		if updated_result is not None and updated_result != self.result:
			self.result = updated_result
			self.locationLabel.SetLabel(_("Location: {location}").format(location=self.result.format_location()))
			self.Layout()


def initialize_com_for_thread():
	try:
		import pythoncom

		pythoncom.CoInitialize()
		return pythoncom.CoUninitialize
	except Exception:
		pass
	try:
		import comtypes

		comtypes.CoInitialize()
		return comtypes.CoUninitialize
	except Exception:
		pass
	try:
		import ctypes

		ctypes.windll.ole32.CoInitialize(None)
		return ctypes.windll.ole32.CoUninitialize
	except Exception:
		return lambda: None

def get_docx_visual_locations(path, results, extracted_text):
	uninitialize_com = initialize_com_for_thread()
	try:
		word = get_word_application()
		word.Visible = True
		document = word.Documents.Open(str(path))
		document.Activate()
		locations = {}
		for index, result in enumerate(results):
			if select_docx_match_in_word(word, result, extracted_text):
				selection = word.Selection
				page = selection.Information(3)
				visual_line = selection.Information(10)
				locations[index] = (page, visual_line)
		return locations
	finally:
		uninitialize_com()


def select_docx_match_in_word(word, result, extracted_text):
	matched_text = extracted_text[result.start:result.end]
	if not matched_text:
		return False
	selection = word.Selection
	selection.HomeKey(Unit=6)
	find = selection.Find
	find.ClearFormatting()
	find.Text = matched_text
	find.Forward = True
	find.Wrap = 0
	occurrence = extracted_text[:result.start].count(matched_text) + 1
	for _attempt in range(occurrence):
		if not find.Execute():
			return False
	return True

def open_result_file(result, extracted_text=None):
	if result.path.suffix.lower() == ".docx":
		if extracted_text is None:
			try:
				extracted_text = extract_text(result.path).text
			except Exception:
				log_exception("Folder Text Finder could not extract DOCX text before opening in Word.")
				open_file_or_select(result.path)
				return result
		updated_result = open_docx_result_in_word(result, extracted_text)
		if updated_result is not None:
			return updated_result
		ui.message(_("Could not open this DOCX in Word. Opened the file normally."))
	open_file_or_select(result.path)
	return result


def open_docx_result_in_word(result, extracted_text):
	try:
		locations = get_docx_visual_locations(result.path, [result], extracted_text)
		location = locations.get(0)
		if location:
			page, visual_line = location
			ui.message(_("Opened in Word at page {page}, visual line {line}.").format(page=page, line=visual_line))
			return replace(result, page=page, line=visual_line, column=0, location_unit="Visual line")
		ui.message(_("Opened in Word, but Word did not report a page or visual line."))
		return result
	except Exception:
		log_exception("Folder Text Finder could not open DOCX result in Word.")
		return None


def get_word_application():
	try:
		import win32com.client

		return win32com.client.Dispatch("Word.Application")
	except Exception as win32_error:
		try:
			import comtypes.client

			return comtypes.client.CreateObject("Word.Application")
		except Exception as comtypes_error:
			raise RuntimeError(f"win32com failed: {win32_error}; comtypes failed: {comtypes_error}") from comtypes_error


def open_file_or_select(path):
	try:
		os.startfile(str(path))
	except Exception:
		subprocess.Popen(["explorer.exe", "/select,", str(path)])


class StatisticsDialog(wx.Dialog):
	def __init__(self, parent, report):
		super().__init__(parent, title=_("Search Statistics"))
		self.report = report
		sizer = wx.BoxSizer(wx.VERTICAL)
		self.reportCtrl = wx.TextCtrl(self, value=report, style=wx.TE_MULTILINE | wx.TE_READONLY)
		sizer.Add(self.reportCtrl, 1, wx.EXPAND | wx.ALL, 8)
		buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
		copyButton = wx.Button(self, label=_("&Copy Statistics to Clipboard"))
		closeButton = wx.Button(self, wx.ID_CLOSE)
		buttonSizer.Add(copyButton, 0, wx.ALL, 4)
		buttonSizer.Add(closeButton, 0, wx.ALL, 4)
		sizer.Add(buttonSizer, 0, wx.ALIGN_RIGHT | wx.ALL, 4)
		self.SetSizer(sizer)
		self.SetSize((750, 500))
		copyButton.Bind(wx.EVT_BUTTON, self.on_copy)
		closeButton.Bind(wx.EVT_BUTTON, lambda evt: self.Destroy())

	def on_copy(self, evt):
		if wx.TheClipboard.Open():
			wx.TheClipboard.SetData(wx.TextDataObject(self.report))
			wx.TheClipboard.Close()
			ui.message(_("Search statistics copied to clipboard."))


def format_result_for_list(result):
	return _("{file}, {location}, {path}, preview: {preview}").format(
		file=result.path.name,
		location=result.format_location(),
		path=result.path,
		preview=result.preview,
	)


def render_invisible_text(text):
	if not text:
		return ""
	return (
		text.replace("\\", "\\\\")
		.replace("\r\n", "<newline>")
		.replace("\r", "<carriage return>")
		.replace("\n", "<newline>\n")
		.replace("\t", "<tab>")
		.replace(" ", "<space>")
	)
