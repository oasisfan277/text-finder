import os
import subprocess
import threading
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


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = _("Folder Text Finder")

	def __init__(self):
		super().__init__()
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
		folder = get_current_explorer_folder()
		if not folder:
			ui.message(_("Open a folder or focus a file before using Folder Text Finder."))
			return
		wx.CallAfter(FolderTextFinderDialog, gui.mainFrame, folder)


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
		import win32com.client

		GA_ROOT = 2
		foreground_hwnd = ctypes.windll.user32.GetForegroundWindow()
		foreground_root = ctypes.windll.user32.GetAncestor(foreground_hwnd, GA_ROOT) or foreground_hwnd
		shell = win32com.client.Dispatch("Shell.Application")
		candidate_folders = []
		for window in shell.Windows():
			try:
				folder = normalize_search_folder(window.LocationURL)
				if not folder:
					continue
				candidate_folders.append(folder)
				if int(window.HWND) == foreground_root:
					return folder
			except Exception:
				continue
		if len(candidate_folders) == 1:
			return candidate_folders[0]
	except Exception:
		return None
	return None


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

class FolderTextFinderDialog(wx.Dialog):
	def __init__(self, parent, folder):
		super().__init__(parent, title=_("Folder Text Finder"))
		self.folder = folder
		self.results = []
		self.statistics = None
		self._lastQueryValue = ""
		self._build()
		self.CentreOnScreen()
		self.Show()

	def _build(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(wx.StaticText(self, label=_("Folder: {folder}").format(folder=self.folder)), 0, wx.ALL, 8)

		mainSizer.Add(wx.StaticText(self, label=_("&Search text:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.queryCtrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER)
		mainSizer.Add(self.queryCtrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
		mainSizer.Add(wx.StaticText(self, label=_("Search text &preview:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.previewCtrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
		mainSizer.Add(self.previewCtrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

		self.wholeWordCtrl = wx.CheckBox(self, label=_("&Whole word search"))
		self.caseCtrl = wx.CheckBox(self, label=_("&Case sensitive"))
		self.subfoldersCtrl = wx.CheckBox(self, label=_("Include &subfolders"))
		self.reportPagesCtrl = wx.CheckBox(self, label=_("Report &page numbers when available"))
		self.reportPagesCtrl.SetValue(get_setting("reportPageNumbers"))
		self.filterCtrl = wx.TextCtrl(self, value=DEFAULT_FILE_FILTERS)

		mainSizer.Add(self.wholeWordCtrl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		mainSizer.Add(self.caseCtrl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		mainSizer.Add(self.subfoldersCtrl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		mainSizer.Add(self.reportPagesCtrl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		mainSizer.Add(wx.StaticText(self, label=_("File name &filters:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		mainSizer.Add(self.filterCtrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

		self.resultsCtrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
		for index, label in enumerate((_("File"), _("Location"), _("Preview"))):
			self.resultsCtrl.InsertColumn(index, label)
		mainSizer.Add(self.resultsCtrl, 1, wx.EXPAND | wx.ALL, 8)

		buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.searchButton = wx.Button(self, label=_("&Search"))
		self.openButton = wx.Button(self, label=_("&Open Result"))
		self.statsButton = wx.Button(self, label=_("Search &Statistics"))
		self.closeButton = wx.Button(self, wx.ID_CLOSE)
		for button in (self.searchButton, self.openButton, self.statsButton, self.closeButton):
			buttonSizer.Add(button, 0, wx.ALL, 4)
		mainSizer.Add(buttonSizer, 0, wx.ALIGN_RIGHT | wx.ALL, 4)

		self.SetSizer(mainSizer)
		self.SetSize((900, 650))

		self.searchButton.Bind(wx.EVT_BUTTON, self.on_search)
		self.openButton.Bind(wx.EVT_BUTTON, self.on_open_result)
		self.statsButton.Bind(wx.EVT_BUTTON, self.on_statistics)
		self.closeButton.Bind(wx.EVT_BUTTON, lambda evt: self.Destroy())
		self.queryCtrl.Bind(wx.EVT_CHAR_HOOK, self.on_query_char_hook)
		self.queryCtrl.Bind(wx.EVT_TEXT, self.on_query_text)
		self.resultsCtrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_open_result)

	def on_search(self, evt):
		query = self.queryCtrl.GetValue()
		if not query:
			ui.message(_("Enter text to search for."))
			return
		self.searchButton.Disable()
		self.resultsCtrl.DeleteAllItems()
		ui.message(_("Searching."))
		options = SearchOptions(
			query=query,
			whole_word=self.wholeWordCtrl.GetValue(),
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
		for result in results:
			index = self.resultsCtrl.InsertItem(self.resultsCtrl.GetItemCount(), result.path.name)
			location = result.format_location()
			self.resultsCtrl.SetItem(index, 1, location)
			self.resultsCtrl.SetItem(index, 2, result.preview)
		for column in range(3):
			self.resultsCtrl.SetColumnWidth(column, wx.LIST_AUTOSIZE_USEHEADER)
		self.searchButton.Enable()
		ui.message(statistics.summary_message())

	def on_open_result(self, evt):
		index = self.resultsCtrl.GetFirstSelected()
		if index < 0 or index >= len(self.results):
			ui.message(_("Select a result first."))
			return
		path = self.results[index].path
		try:
			os.startfile(str(path))
		except Exception:
			subprocess.Popen(["explorer.exe", "/select,", str(path)])

	def on_statistics(self, evt):
		if not self.statistics:
			ui.message(_("No search statistics are available yet."))
			return
		StatisticsDialog(self, self.statistics.to_report()).Show()


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
