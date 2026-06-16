import os
import subprocess
import json
import tempfile
import threading
import traceback
import ctypes
import time
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
from .text_extractors import (
	SUPPORTED_FILE_TYPES,
	TextExtractionError,
	all_supported_extensions,
	extract_text,
)


try:
	_
except NameError:
	_ = lambda text: text


CONFIG_SECTION = "textFinder"
WORD_LOCATION_BATCH_SIZE = 10
WORD_AUTO_LOCATION_LIMIT = 50


def _initialize_config():
	if config is None:
		return
	config.conf.spec[CONFIG_SECTION] = {
		"allowDirectTabsAndLineBreaks": "boolean(default=False)",
		"announceInvisibleCharacters": "boolean(default=False)",
		"reportPageNumbers": "boolean(default=True)",
		"showFullPath": "boolean(default=False)",
		"searchWholeWord": "boolean(default=False)",
		"searchCaseSensitive": "boolean(default=False)",
		"searchIncludeSubfolders": "boolean(default=False)",
		"searchAllFileTypes": "boolean(default=True)",
		"searchFileTypes": "string(default='')",
	}


SETTING_DEFAULTS = {
	"allowDirectTabsAndLineBreaks": False,
	"announceInvisibleCharacters": False,
	"reportPageNumbers": True,
	"showFullPath": False,
	"searchWholeWord": False,
	"searchCaseSensitive": False,
	"searchIncludeSubfolders": False,
	"searchAllFileTypes": True,
	"searchFileTypes": "",
}


def parse_extension_list(value):
	extensions = []
	for part in (value or "").split(";"):
		part = part.strip().lower()
		if not part:
			continue
		if not part.startswith("."):
			part = "." + part
		if part not in extensions:
			extensions.append(part)
	return extensions


def get_active_file_patterns():
	# Build the search file filters from the settings panel choice instead of a
	# per-search text box. "All supported file types" searches every type Text
	# Finder understands; otherwise only the user's selected types are searched.
	if get_setting("searchAllFileTypes"):
		selected = all_supported_extensions()
	else:
		selected = tuple(parse_extension_list(get_setting("searchFileTypes")))
		if not selected:
			# Nothing chosen falls back to all supported types so a search is
			# never silently empty.
			selected = all_supported_extensions()
	return tuple("*{ext}".format(ext=ext) for ext in selected)



def file_type_is_selected(search_all, selected_extensions, extensions):
	return search_all or any(ext in selected_extensions for ext in extensions)

def file_type_choice_label(label, selected):
	state = _("Selected") if selected else _("Not selected")
	return _("{state}: {label}").format(state=state, label=label)


def ordered_supported_file_types(search_all, selected_extensions):
	if search_all or not selected_extensions:
		return list(SUPPORTED_FILE_TYPES)
	selected = []
	unselected = []
	for label, extensions in SUPPORTED_FILE_TYPES:
		if any(ext in selected_extensions for ext in extensions):
			selected.append((label, extensions))
		else:
			unselected.append((label, extensions))
	return selected + unselected


def get_setting(name):
	try:
		return config.conf[CONFIG_SECTION][name]
	except Exception:
		return SETTING_DEFAULTS[name]


def set_setting(name, value):
	if config is None:
		return
	try:
		config.conf[CONFIG_SECTION][name] = value
	except Exception:
		log_exception("Text Finder could not save the {name} setting.".format(name=name))


def save_config():
	if config is None:
		return
	try:
		config.conf.save()
	except Exception:
		log_exception("Text Finder could not persist its configuration.")


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
	scriptCategory = _("Text Finder")

	def __init__(self):
		super().__init__()
		self._dialog = None
		if NVDASettingsDialog and TextFinderSettingsPanel not in NVDASettingsDialog.categoryClasses:
			NVDASettingsDialog.categoryClasses.append(TextFinderSettingsPanel)

	def terminate(self):
		if NVDASettingsDialog and TextFinderSettingsPanel in NVDASettingsDialog.categoryClasses:
			NVDASettingsDialog.categoryClasses.remove(TextFinderSettingsPanel)
		super().terminate()

	@scriptHandler.script(
		description=_("Search files containing text in the current file or folder"),
		gesture="kb:NVDA+alt+f",
	)
	def script_openTextFinder(self, gesture):
		ui.message(_("Text Finder starting."))
		log_info("Text Finder command started.")
		try:
			target = get_current_search_target()
		except Exception:
			log_exception("Text Finder target detection crashed.")
			ui.message(_("Text Finder could not detect the file or folder."))
			return
		if not target:
			log_folder_detection_diagnostics()
			ui.message(_("Open a folder, focus a file, or open a supported Office document before using Text Finder."))
			return
		log_info("Text Finder opening dialog for target: %s", target)
		wx.CallAfter(self._show_dialog, target)

	def _show_dialog(self, target):
		if self._dialog:
			try:
				self._dialog.Destroy()
			except Exception as exc:
				pass
		self._dialog = TextFinderDialog(gui.mainFrame, target)
		self._dialog.Bind(wx.EVT_WINDOW_DESTROY, self._on_dialog_destroy)
		self._dialog.present()

	def _on_dialog_destroy(self, evt):
		if evt.GetEventObject() is self._dialog:
			self._dialog = None
		evt.Skip()


class TextFinderSettingsPanel(SettingsPanel):
	title = _("Text Finder")

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
		self.showFullPathCtrl = settingsSizerHelper.addItem(
			wx.CheckBox(self, label=_("Show the full file path in search results"))
		)
		self.showFullPathCtrl.SetValue(get_setting("showFullPath"))

		self.searchAllFileTypesCtrl = settingsSizerHelper.addItem(
			wx.CheckBox(self, label=_("Search all supported file types"))
		)
		self.searchAllFileTypesCtrl.SetValue(get_setting("searchAllFileTypes"))
		self.searchAllFileTypesCtrl.Bind(wx.EVT_CHECKBOX, self.on_toggle_all_file_types)

		selected_extensions = set(parse_extension_list(get_setting("searchFileTypes")))
		select_all_types = get_setting("searchAllFileTypes")
		self.fileTypeChoices = ordered_supported_file_types(select_all_types, selected_extensions)
		self.fileTypesCtrl = settingsSizerHelper.addLabeledControl(
			_("File types to search:"),
			wx.CheckListBox,
			choices=[file_type_choice_label(label, False) for label, _extensions in self.fileTypeChoices],
		)
		self.fileTypesCtrl.Bind(wx.EVT_CHECKLISTBOX, self.on_file_type_checked)
		for index, (_label, extensions) in enumerate(self.fileTypeChoices):
			self.fileTypesCtrl.Check(index, file_type_is_selected(select_all_types, selected_extensions, extensions))
		self._update_file_type_choice_labels()
		self._update_file_types_enabled()

	def on_toggle_all_file_types(self, evt):
		check_all = self.searchAllFileTypesCtrl.GetValue()
		for index in range(len(self.fileTypeChoices)):
			self.fileTypesCtrl.Check(index, check_all)
		self._update_file_type_choice_labels()
		self._update_file_types_enabled()
		evt.Skip()

	def on_file_type_checked(self, evt):
		self._update_file_type_choice_labels()
		evt.Skip()

	def _update_file_type_choice_labels(self):
		for index, (label, _extensions) in enumerate(self.fileTypeChoices):
			self.fileTypesCtrl.SetString(index, file_type_choice_label(label, self.fileTypesCtrl.IsChecked(index)))

	def _update_file_types_enabled(self):
		self.fileTypesCtrl.Enable(not self.searchAllFileTypesCtrl.GetValue())

	def onSave(self):
		config.conf[CONFIG_SECTION]["allowDirectTabsAndLineBreaks"] = self.allowDirectTabsAndLineBreaksCtrl.GetValue()
		config.conf[CONFIG_SECTION]["announceInvisibleCharacters"] = self.announceInvisibleCharactersCtrl.GetValue()
		config.conf[CONFIG_SECTION]["reportPageNumbers"] = self.reportPageNumbersCtrl.GetValue()
		config.conf[CONFIG_SECTION]["showFullPath"] = self.showFullPathCtrl.GetValue()
		config.conf[CONFIG_SECTION]["searchAllFileTypes"] = self.searchAllFileTypesCtrl.GetValue()
		chosen_extensions = []
		for index, (_label, extensions) in enumerate(self.fileTypeChoices):
			if self.fileTypesCtrl.IsChecked(index):
				chosen_extensions.extend(extensions)
		config.conf[CONFIG_SECTION]["searchFileTypes"] = ";".join(chosen_extensions)

def get_current_search_target():
	target = get_target_from_focused_object()
	if target:
		return target
	target = get_open_document_target()
	if target:
		return target
	return get_foreground_explorer_target_from_shell()


def get_current_explorer_folder():
	return get_current_search_target()


def get_target_from_focused_object():
	try:
		import api

		objects = [api.getFocusObject(), api.getForegroundObject()]
		seen = set()
		for obj in objects:
			while obj and id(obj) not in seen:
				seen.add(id(obj))
				for attr in ("location", "value", "name"):
					target = normalize_search_target(getattr(obj, attr, None))
					if target:
						return target
				obj = getattr(obj, "parent", None)
	except Exception:
		pass
	return None


def get_foreground_explorer_target_from_shell():
	try:
		import ctypes

		GA_ROOT = 2
		foreground_hwnd = ctypes.windll.user32.GetForegroundWindow()
		foreground_root = ctypes.windll.user32.GetAncestor(foreground_hwnd, GA_ROOT) or foreground_hwnd
		shell = get_shell_application()
		candidate_targets = []
		selected_targets = []
		for window in shell.Windows():
			try:
				selected_target = get_selected_target_from_shell_window(window)
				target = selected_target or normalize_search_target(window.LocationURL)
				if not target:
					continue
				candidate_targets.append(target)
				if selected_target:
					selected_targets.append(selected_target)
				if int(window.HWND) == foreground_root:
					return target
			except Exception:
				continue
		if len(selected_targets) == 1:
			return selected_targets[0]
		if len(candidate_targets) == 1:
			return candidate_targets[0]
	except Exception:
		return None
	return None


def get_selected_target_from_shell_window(window):
	try:
		selected_items = window.Document.SelectedItems()
		if selected_items.Count != 1:
			return None
		return normalize_search_target(selected_items.Item(0).Path)
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


def normalize_search_target(candidate):
	if not candidate:
		return None
	path = path_from_shell_location_url(str(candidate).strip().strip('"'))
	path = os.path.expandvars(path)
	if os.path.isfile(path) or os.path.isdir(path):
		return path
	return None

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




def get_open_document_target():
	app_name = get_foreground_app_name()
	if app_name in {"winword", "word"}:
		target = get_open_word_document_target_from_nvda()
		if target:
			return target
	app_order = []
	if app_name in {"winword", "word"}:
		app_order.append("winword")
	elif app_name in {"excel"}:
		app_order.append("excel")
	elif app_name in {"powerpnt", "powerpoint"}:
		app_order.append("powerpnt")
	# If NVDA does not expose the app name clearly, try the common Office apps
	# without starting new instances. get_running_com_application only attaches
	# to an already-running app.
	for fallback in ("winword", "excel", "powerpnt"):
		if fallback not in app_order:
			app_order.append(fallback)
	for office_app in app_order:
		target = get_office_active_document_target(office_app)
		if target:
			return target
	return None


def get_foreground_app_name():
	try:
		import api

		for obj in (api.getFocusObject(), api.getForegroundObject(), api.getNavigatorObject()):
			app_module = getattr(obj, "appModule", None)
			app_name = getattr(app_module, "appName", None)
			if app_name:
				return str(app_name).lower()
	except Exception:
		pass
	return ""


def get_open_word_document_target_from_nvda():
	document_name = get_foreground_document_file_name({"winword", "word"})
	if not document_name:
		return None
	return find_matching_file_in_shell_windows(document_name)


def get_foreground_document_file_name(app_names):
	try:
		import api

		for obj in (api.getFocusObject(), api.getForegroundObject(), api.getNavigatorObject()):
			current = obj
			seen = set()
			while current and id(current) not in seen:
				seen.add(id(current))
				app_module = getattr(current, "appModule", None)
				app_name = str(getattr(app_module, "appName", "") or "").lower()
				if app_name in app_names:
					name = word_file_name_from_object_name(getattr(current, "name", None))
					if name:
						return name
				current = getattr(current, "parent", None)
	except Exception:
		pass
	return None


def word_file_name_from_object_name(name):
	if not name:
		return None
	name = str(name).strip()
	if name.endswith(" - Word"):
		name = name[:-7].strip()
	for suffix in (".docx", ".docm", ".doc", ".rtf"):
		index = name.lower().find(suffix)
		if index >= 0:
			return name[: index + len(suffix)]
	return None


def find_matching_file_in_shell_windows(file_name):
	matches = []
	selected_matches = []
	try:
		shell = get_shell_application()
		for window in shell.Windows():
			try:
				selected_items = window.Document.SelectedItems()
				for index in range(selected_items.Count):
					path = normalize_search_target(selected_items.Item(index).Path)
					if path and os.path.basename(path).lower() == file_name.lower():
						selected_matches.append(path)
						matches.append(path)
			except Exception:
				pass
			try:
				folder = normalize_search_folder(window.LocationURL)
				if folder:
					path = normalize_search_target(os.path.join(folder, file_name))
					if path:
						matches.append(path)
			except Exception:
				pass
	except Exception:
		return None
	for candidates in (selected_matches, matches):
		unique = []
		for path in candidates:
			if path not in unique:
				unique.append(path)
		if len(unique) == 1:
			return unique[0]
	return None


def get_office_active_document_target(app_name):
	try:
		if app_name == "winword":
			word = get_running_com_application("Word.Application")
			return get_word_active_document_path(word)
		if app_name == "excel":
			excel = get_running_com_application("Excel.Application")
			return normalize_search_target(excel.ActiveWorkbook.FullName)
		if app_name == "powerpnt":
			powerpoint = get_running_com_application("PowerPoint.Application")
			return normalize_search_target(powerpoint.ActivePresentation.FullName)
	except Exception:
		log_exception("Text Finder could not detect the active Office document.")
	return None


def get_running_com_application(prog_id):
	try:
		import win32com.client

		return win32com.client.GetActiveObject(prog_id)
	except Exception as win32_error:
		try:
			import comtypes.client

			return comtypes.client.GetActiveObject(prog_id)
		except Exception as comtypes_error:
			raise RuntimeError(f"win32com failed: {win32_error}; comtypes failed: {comtypes_error}") from comtypes_error


def get_word_active_document_path(word):
	try:
		path = normalize_search_target(word.ActiveDocument.FullName)
		if path:
			return path
	except Exception:
		pass
	try:
		if word.ProtectedViewWindows.Count:
			path = normalize_search_target(word.ActiveProtectedViewWindow.Document.FullName)
			if path:
				return path
	except Exception:
		pass
	return None


def log_folder_detection_diagnostics():
	try:
		import api
		import logHandler

		log = logHandler.log
		log.info("Text Finder folder detection failed. Starting diagnostics.")
		for label, obj in (("focus", api.getFocusObject()), ("foreground", api.getForegroundObject()), ("navigator", api.getNavigatorObject())):
			log.info("Text Finder %s object chain:", label)
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
			logHandler.log.error("Text Finder diagnostics failed:\n%s", traceback.format_exc())
		except Exception:
			pass


def log_shell_window_diagnostics(log):
	try:
		import ctypes

		GA_ROOT = 2
		foreground_hwnd = ctypes.windll.user32.GetForegroundWindow()
		foreground_root = ctypes.windll.user32.GetAncestor(foreground_hwnd, GA_ROOT) or foreground_hwnd
		log.info("Text Finder foreground hwnd=%r root=%r", foreground_hwnd, foreground_root)
		shell = get_shell_application()
		for index, window in enumerate(shell.Windows()):
			try:
				log.info("Text Finder shell window %s hwnd=%r url=%r normalized=%r", index, int(window.HWND), window.LocationURL, normalize_search_folder(window.LocationURL))
				selected_items = window.Document.SelectedItems()
				log.info("Text Finder shell window %s selected count=%r", index, selected_items.Count)
				for item_index in range(selected_items.Count):
					item = selected_items.Item(item_index)
					log.info("Text Finder selected item %s path=%r normalized=%r", item_index, item.Path, normalize_search_folder(item.Path))
			except Exception:
				log.info("Text Finder shell window %s diagnostics failed:\n%s", index, traceback.format_exc())
	except Exception:
		log.info("Text Finder shell diagnostics failed:\n%s", traceback.format_exc())

def log_search_issue_details(statistics):
	for label, entries in (
		("unsupported", statistics.unsupported_files),
		("no extractable text", statistics.no_extractable_text_files),
		("unreadable", statistics.unreadable_files),
	):
		for path, reason in entries[:5]:
			log_info("Text Finder search %s file: %s; reason: %s", label, path, reason)


class TextFinderDialog(wx.Dialog):
	def __init__(self, parent, target):
		super().__init__(parent, title=_("Text Finder"))
		self.target = target
		self.folder = target
		self.results = []
		self.statistics = None
		self._lastQueryValue = ""
		self._search_generation = 0
		self._build()
		self.CentreOnScreen()

	def present(self):
		self.Show()
		self.Raise()
		self.SetFocus()
		self.queryCtrl.SetFocus()
		ui.message(_("Text Finder opened. Search target: {folder}").format(folder=self.folder))
		log_info("Text Finder dialog presented for target: %s", self.folder)

	def _build(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(wx.StaticText(self, label=_("Search target: {target}").format(target=self.target)), 0, wx.ALL, 8)

		mainSizer.Add(wx.StaticText(self, label=_("Search &text:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.queryCtrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER)
		mainSizer.Add(self.queryCtrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
		mainSizer.Add(wx.StaticText(self, label=_("Search text &preview:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.previewCtrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
		mainSizer.Add(self.previewCtrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

		searchModeSizer = wx.StaticBoxSizer(wx.VERTICAL, self, _("Search mode"))
		whole_word = get_setting("searchWholeWord")
		self.exactFragmentCtrl = wx.RadioButton(self, label=_("Exact &fragment"), style=wx.RB_GROUP)
		self.exactWholeWordCtrl = wx.RadioButton(self, label=_("Exact &whole word"))
		self.exactFragmentCtrl.SetValue(not whole_word)
		self.exactWholeWordCtrl.SetValue(whole_word)
		searchModeSizer.Add(self.exactFragmentCtrl, 0, wx.ALL, 4)
		searchModeSizer.Add(self.exactWholeWordCtrl, 0, wx.ALL, 4)
		self.caseCtrl = wx.CheckBox(self, label=_("&Case sensitive"))
		self.caseCtrl.SetValue(get_setting("searchCaseSensitive"))
		self.subfoldersCtrl = wx.CheckBox(self, label=_("Include subfol&ders"))
		self.subfoldersCtrl.SetValue(get_setting("searchIncludeSubfolders"))
		self.reportPagesCtrl = wx.CheckBox(self, label=_("Report page &numbers when available"))
		self.reportPagesCtrl.SetValue(get_setting("reportPageNumbers"))

		mainSizer.Add(searchModeSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)
		mainSizer.Add(self.caseCtrl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		mainSizer.Add(self.subfoldersCtrl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		mainSizer.Add(self.reportPagesCtrl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		# File types to search are chosen in the NVDA settings panel, not here.

		mainSizer.Add(wx.StaticText(self, label=_("Search &results:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.resultsCtrl = wx.ListBox(self, style=wx.LB_SINGLE)
		mainSizer.Add(self.resultsCtrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
		self.wordStatusLabel = wx.StaticText(self, label=_("Word location &status:"))
		mainSizer.Add(self.wordStatusLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		self.wordStatusCtrl = wx.TextCtrl(self, value=_("Not started."), style=wx.TE_READONLY)
		mainSizer.Add(self.wordStatusCtrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

		buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.searchButton = wx.Button(self, label=_("&Search"))
		self.openFileButton = wx.Button(self, label=_("Open Fi&le"))
		self.goToResultButton = wx.Button(self, label=_("&Go to Search Result"))
		self.openButton = wx.Button(self, label=_("&Open Result"))
		self.statsButton = wx.Button(self, label=_("Search Stat&istics"))
		self.closeButton = wx.Button(self, wx.ID_CLOSE)
		for button in (self.searchButton, self.openFileButton, self.goToResultButton, self.openButton, self.statsButton, self.closeButton):
			buttonSizer.Add(button, 0, wx.ALL, 4)
		mainSizer.Add(buttonSizer, 0, wx.ALIGN_RIGHT | wx.ALL, 4)

		self.SetSizer(mainSizer)
		self.SetSize((900, 650))

		self.searchButton.Bind(wx.EVT_BUTTON, self.on_search)
		self.openFileButton.Bind(wx.EVT_BUTTON, self.on_open_file_from_result)
		self.goToResultButton.Bind(wx.EVT_BUTTON, self.on_go_to_result)
		self.openButton.Bind(wx.EVT_BUTTON, self.on_open_result)
		self.statsButton.Bind(wx.EVT_BUTTON, self.on_statistics)
		self.closeButton.Bind(wx.EVT_BUTTON, lambda evt: self.Destroy())
		self.Bind(wx.EVT_CHAR_HOOK, self.on_dialog_char_hook)
		self.queryCtrl.Bind(wx.EVT_CHAR_HOOK, self.on_query_char_hook)
		self.queryCtrl.Bind(wx.EVT_TEXT, self.on_query_text)
		self.resultsCtrl.Bind(wx.EVT_LISTBOX_DCLICK, self.on_open_result)
		self.resultsCtrl.Bind(wx.EVT_CHAR_HOOK, self.on_results_char_hook)
		self.update_action_button_visibility()

	def update_action_button_visibility(self):
		is_file_search = Path(self.target).is_file()
		is_word_file_search = is_file_search and Path(self.target).suffix.lower() == ".docx"
		self.subfoldersCtrl.Show(not is_file_search)
		self.openFileButton.Show(not is_word_file_search)
		self.openButton.Show(not is_word_file_search)
		self.goToResultButton.Show(is_word_file_search)
		show_word_status = self._has_docx_results(self.results)
		self.wordStatusLabel.Show(show_word_status)
		self.wordStatusCtrl.Show(show_word_status)
		self.Layout()

	def on_search(self, evt):
		query = self.queryCtrl.GetValue()
		if not query:
			ui.message(_("Enter text to search for."))
			return
		self.searchButton.Disable()
		self.resultsCtrl.Clear()
		self.results = []
		self.set_word_status(_("Not started."))
		ui.message(_("Searching."))
		options = SearchOptions(
			query=query,
			whole_word=self.exactWholeWordCtrl.GetValue(),
			case_sensitive=self.caseCtrl.GetValue(),
			include_subfolders=False if Path(self.target).is_file() else self.subfoldersCtrl.GetValue(),
			file_patterns=get_active_file_patterns(),
			report_page_numbers=self.reportPagesCtrl.GetValue(),
		)
		self._save_search_options(options)
		log_info(
			"Text Finder search started. mode=%s case_sensitive=%s include_subfolders=%s filter_count=%d query_length=%d report_pages=%s",
			"whole word" if options.whole_word else "fragment",
			options.case_sensitive,
			options.include_subfolders,
			len(options.file_patterns),
			len(options.query),
			options.report_page_numbers,
		)
		thread = threading.Thread(target=self._run_search, args=(options,), daemon=True)
		thread.start()

	def _save_search_options(self, options):
		set_setting("searchWholeWord", options.whole_word)
		set_setting("searchCaseSensitive", options.case_sensitive)
		set_setting("searchIncludeSubfolders", options.include_subfolders)
		set_setting("reportPageNumbers", options.report_page_numbers)
		save_config()

	def on_query_char_hook(self, evt):
		key_code = evt.GetKeyCode()
		if key_code == wx.WXK_ESCAPE:
			self.Destroy()
			return
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

	def on_dialog_char_hook(self, evt):
		if evt.GetKeyCode() == wx.WXK_ESCAPE:
			self.Destroy()
			return
		evt.Skip()

	def _run_search(self, options):
		searcher = Searcher(self.target, options)
		results, statistics = searcher.search()
		wx.CallAfter(self._finish_search, results, statistics)

	def _finish_search(self, results, statistics):
		self.results = results
		self.statistics = statistics
		self._search_generation += 1
		self.refresh_results_list()
		self.searchButton.Enable()
		self.update_action_button_visibility()
		has_docx = self._has_docx_results(results)
		log_info(
			"Text Finder search complete. target=%s exists=%s is_file=%s suffix=%s results=%d files_with_matches=%d supported=%d unsupported=%d no_text=%d unreadable=%d duration=%.2f has_docx=%s",
			statistics.folder,
			statistics.folder.exists(),
			statistics.folder.is_file(),
			statistics.folder.suffix,
			len(results),
			len(statistics.files_with_matches),
			statistics.supported_files_searched,
			len(statistics.unsupported_files),
			len(statistics.no_extractable_text_files),
			len(statistics.unreadable_files),
			statistics.duration,
			has_docx,
		)
		log_search_issue_details(statistics)
		# Reveal the results straight away so they are usable, then fill the Word
		# page and visual line numbers in the background, updating each result in
		# place as Word reports it.
		if results:
			self.resultsCtrl.SetSelection(0)
			self.resultsCtrl.SetFocus()
		ui.message(statistics.summary_message())
		if has_docx:
			self.start_word_location_enrichment(results, self._search_generation)

	def _has_docx_results(self, results):
		return any(result.path.suffix.lower() == ".docx" for result in results)

	def start_word_location_enrichment(self, results, generation):
		docx_count = sum(1 for result in results if result.path.suffix.lower() == ".docx")
		limited_count = min(docx_count, WORD_AUTO_LOCATION_LIMIT)
		log_info("Text Finder getting Word locations for %d of %d DOCX results in the background.", limited_count, docx_count)
		if limited_count < docx_count:
			self.set_word_status(_("Getting Word page and visual line numbers for the first {count} of {total} results.").format(count=limited_count, total=docx_count))
		else:
			self.set_word_status(_("Getting Word page and visual line numbers for {total} results.").format(total=docx_count))
		thread = threading.Thread(target=self.enrich_word_locations, args=(results, generation), daemon=True)
		thread.start()

	def enrich_word_locations(self, original_results, generation):
		all_docx_indices = [index for index, result in enumerate(original_results) if result.path.suffix.lower() == ".docx"]
		skipped_indices = all_docx_indices[WORD_AUTO_LOCATION_LIMIT:]
		if skipped_indices:
			wx.CallAfter(self.clear_word_pending, generation, skipped_indices)
		indices_by_path = {}
		for index in all_docx_indices[:WORD_AUTO_LOCATION_LIMIT]:
			result = original_results[index]
			indices_by_path.setdefault(result.path, []).append(index)
		docx_count = sum(len(indices) for indices in indices_by_path.values())
		total_docx_count = len(all_docx_indices)
		counters = {"updated_total": 0}
		# Reuse a single hidden Word instance for the whole run instead of starting
		# and quitting Word once per file. Each document is walked in one forward
		# pass (see collect_docx_visual_locations) rather than restarting Word's
		# Find from the top for every batch, which is what made large documents
		# (hundreds of matches) take minutes or never finish.
		uninitialize_com = initialize_com_for_thread()
		word = None
		try:
			for path, indices in indices_by_path.items():
				if not self.is_search_generation_current(generation):
					return
				try:
					extracted_text = extract_text(path).text
				except Exception:
					log_exception("Text Finder could not extract DOCX text before enriching result locations.")
					wx.CallAfter(self.clear_word_pending, generation, list(indices))
					continue
				results_for_path = [original_results[index] for index in indices]
				# Buffer per-result outcomes and flush them to the list in chunks so
				# results fill in progressively while the single forward pass runs.
				pending = {"updates": {}, "cleared": []}
				handled = set()

				def flush():
					if not pending["updates"] and not pending["cleared"]:
						return
					updates = pending["updates"]
					cleared = pending["cleared"]
					counters["updated_total"] += len(updates)
					wx.CallAfter(self.apply_word_locations, generation, updates, cleared)
					wx.CallAfter(self.announce_word_enrichment_progress, generation, counters["updated_total"], docx_count, total_docx_count)
					pending["updates"] = {}
					pending["cleared"] = []

				def on_result(local_index, location, _indices=indices):
					global_index = _indices[local_index]
					handled.add(global_index)
					if location is None:
						# Any result Word did not report stops loading and falls back to Open Result.
						pending["cleared"].append(global_index)
					else:
						pending["updates"][global_index] = location
					if len(pending["updates"]) + len(pending["cleared"]) >= WORD_LOCATION_BATCH_SIZE:
						flush()

				document = None
				try:
					if word is None:
						word = get_word_application(new_instance=True)
						word.Visible = False
					document = open_word_document_read_only(word, path)
					document.Activate()
					collect_docx_visual_locations(
						word,
						results_for_path,
						extracted_text,
						on_result=on_result,
						should_continue=lambda: self.is_search_generation_current(generation),
					)
				except Exception:
					log_exception("Text Finder could not enrich DOCX result locations in the background.")
				finally:
					flush()
					if document is not None:
						try:
							document.Close(False)
						except Exception:
							log_exception("Text Finder could not close the hidden Word document.")
				# Results the pass never reached (a Word error part-way through) stop
				# loading so they fall back to Open Result instead of spinning forever.
				if self.is_search_generation_current(generation):
					unhandled = [index for index in indices if index not in handled]
					if unhandled:
						wx.CallAfter(self.clear_word_pending, generation, unhandled)
		finally:
			if word is not None:
				try:
					word.Quit()
				except Exception:
					log_exception("Text Finder could not close the hidden Word application.")
			uninitialize_com()
		log_info("Text Finder Word location lookup finished. updated=%d of docx=%d", counters["updated_total"], docx_count)
		wx.CallAfter(self.announce_word_enrichment_done, generation, counters["updated_total"], docx_count)

	def apply_word_locations(self, generation, updates, cleared):
		if generation != self._search_generation:
			return
		for result_index, (page, visual_line) in updates.items():
			if 0 <= result_index < len(self.results):
				self.results[result_index] = replace(self.results[result_index], page=page, line=visual_line, column=0, location_unit="Visual line", word_pending=False)
				self.resultsCtrl.SetString(result_index, format_result_for_list(self.results[result_index]))
		self._clear_pending_indices(cleared)

	def clear_word_pending(self, generation, indices):
		if generation != self._search_generation:
			return
		self._clear_pending_indices(indices)

	def _clear_pending_indices(self, indices):
		for result_index in indices:
			if 0 <= result_index < len(self.results) and self.results[result_index].word_pending:
				self.results[result_index] = replace(self.results[result_index], word_pending=False)
				self.resultsCtrl.SetString(result_index, format_result_for_list(self.results[result_index]))

	def announce_word_enrichment_done(self, generation, updated_total, docx_count):
		if generation != self._search_generation:
			return
		if updated_total:
			self.set_word_status(_("Word page and visual line numbers ready for {count} results.").format(count=updated_total))
		elif docx_count:
			self.set_word_status(_("Word page and visual line numbers could not be added. Use Go to Search Result on one result to test Word directly."))

	def announce_word_enrichment_progress(self, generation, updated_total, docx_count, total_docx_count=None):
		if generation != self._search_generation or not updated_total or updated_total >= docx_count:
			return
		total = total_docx_count or docx_count
		self.set_word_status(_("Word page and visual line numbers ready for {done} of first {limit} results. Total Word results: {total}.").format(done=updated_total, limit=docx_count, total=total))

	def set_word_status(self, message):
		self.wordStatusCtrl.SetValue(message)

	def cancel_word_location_enrichment(self):
		self._search_generation += 1
		self.set_word_status(_("Word page and visual line lookup stopped."))

	def is_search_generation_current(self, generation):
		return generation == self._search_generation

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
		if key_code == wx.WXK_ESCAPE:
			self.Destroy()
			return
		if key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			self.activate_selected_result()
			return
		evt.Skip()

	def on_open_result(self, evt):
		self.activate_selected_result()

	def activate_selected_result(self):
		if Path(self.target).is_file() and Path(self.target).suffix.lower() == ".docx":
			self.on_go_to_result(None)
			return
		self.open_selected_result()

	def open_selected_result(self):
		result = self.get_selected_result()
		if result is None:
			return
		log_info("Text Finder opening result text for a %s file.", result.path.suffix.lower() or "no-extension")
		try:
			extracted = extract_text(result.path)
		except TextExtractionError as exc:
			ui.message(_("Could not open result text: {reason}").format(reason=exc.message))
			return
		except Exception:
			log_exception("Text Finder could not open result text.")
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

	def on_go_to_result(self, evt):
		result = self.get_selected_result()
		if result is None:
			return
		if result.path.suffix.lower() != ".docx":
			ui.message(_("Go to Search Result is available for Word documents."))
			return
		self.cancel_word_location_enrichment()
		try:
			extracted_text = extract_text(result.path).text
		except Exception:
			log_exception("Text Finder could not extract DOCX text before going to result.")
			ui.message(_("Could not get the Word result text."))
			return
		updated_result = go_to_word_result(result, extracted_text)
		if updated_result is not None and updated_result != result:
			index = self.resultsCtrl.GetSelection()
			self.results[index] = updated_result
			self.resultsCtrl.SetString(index, format_result_for_list(updated_result))
			self.Destroy()

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
		self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
		self.textCtrl.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
		openFileButton.Bind(wx.EVT_BUTTON, self.on_open_file)
		closeButton.Bind(wx.EVT_BUTTON, lambda evt: self.Destroy())
		wx.CallAfter(self.focus_match)

	def on_char_hook(self, evt):
		if evt.GetKeyCode() == wx.WXK_ESCAPE:
			self.Destroy()
			return
		evt.Skip()

	def focus_match(self):
		start = max(0, min(self.result.start, len(self.text)))
		end = max(start, min(self.result.end, len(self.text)))
		self.Raise()
		self.textCtrl.SetFocus()
		self.textCtrl.SetInsertionPoint(start)
		self.textCtrl.SetSelection(start, end)
		if self.result.location_unit == "Open Result" or self.result.word_pending:
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

def get_docx_visual_locations(path, results, extracted_text, visible=True, close_document=False, quit_word=False, read_only=True, bring_to_front=False):
	uninitialize_com = initialize_com_for_thread()
	word = None
	document = None
	try:
		word = get_word_application(new_instance=not visible or quit_word)
		word.Visible = visible
		document = open_word_document(word, path, read_only=read_only)
		document.Activate()
		locations = collect_docx_visual_locations(word, results, extracted_text)
		if bring_to_front:
			activate_word_window(word, document, path)
		return locations
	finally:
		if close_document and document is not None:
			try:
				document.Close(False)
			except Exception:
				log_exception("Text Finder could not close the hidden Word document.")
		if quit_word and word is not None:
			try:
				word.Quit()
			except Exception:
				log_exception("Text Finder could not close the hidden Word application.")
		uninitialize_com()


def open_word_document_read_only(word, path):
	# FileName, ConfirmConversions, ReadOnly, AddToRecentFiles.
	# ReadOnly lets Word report page and visual line information even when the
	# user already has the document open for editing.
	return open_word_document(word, path, read_only=True, add_to_recent=False)


def open_word_document_editable(word, path):
	return open_word_document(word, path, read_only=False, add_to_recent=True)


def open_word_document(word, path, read_only=True, add_to_recent=False):
	# FileName, ConfirmConversions, ReadOnly, AddToRecentFiles.
	return word.Documents.Open(str(path), False, bool(read_only), bool(add_to_recent))


def get_open_word_visual_locations(path, results, extracted_text, select_result=False):
	requests = []
	for index, result in enumerate(results):
		matched_text = extracted_text[result.start:result.end]
		if not matched_text:
			continue
		requests.append({
			"index": index,
			"text": matched_text,
			"occurrence": extracted_text[:result.start].count(matched_text) + 1,
			"page": result.page,
			"visualLine": result.line if result.location_unit == "Visual line" and not result.word_pending else None,
		})
	if not requests:
		return {}
	payload = {
		"fileName": Path(path).name,
		"fullName": str(Path(path)),
		"requests": requests,
		"selectResult": bool(select_result),
	}
	payload_path = None
	script_path = None
	try:
		with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as payload_file:
			json.dump(payload, payload_file)
			payload_path = payload_file.name
		with tempfile.NamedTemporaryFile("w", delete=False, suffix=".ps1", encoding="utf-8") as script_file:
			script_file.write(OPEN_WORD_LOCATION_SCRIPT)
			script_path = script_file.name
		for executable in powershell_executables():
			try:
				completed = subprocess.run(
					[executable, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path, payload_path],
					capture_output=True,
					text=True,
					encoding="utf-8",
					errors="replace",
					timeout=60,
					creationflags=get_hidden_process_flags(),
				)
			except FileNotFoundError:
				continue
			if completed.returncode != 0:
				log_info("Text Finder open Word location lookup failed: %s", completed.stderr.strip() or completed.stdout.strip())
				return None
			data = json.loads(completed.stdout or "{}")
			return {int(index): tuple(location) for index, location in data.items()}
	except Exception:
		log_exception("Text Finder could not get visual locations from the already-open Word document.")
		return None
	finally:
		for temp_path in (payload_path, script_path):
			if temp_path:
				try:
					os.unlink(temp_path)
				except OSError:
					pass


def powershell_executables():
	windows_dir = os.environ.get("SystemRoot") or os.environ.get("windir") or r"C:\Windows"
	return (
		str(Path(windows_dir) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
		str(Path(windows_dir) / "Sysnative" / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
		"powershell.exe",
	)


def get_hidden_process_flags():
	return getattr(subprocess, "CREATE_NO_WINDOW", 0)


OPEN_WORD_LOCATION_SCRIPT = r'''
param([string] $PayloadPath)
$ErrorActionPreference = 'Stop'
$payload = Get-Content -LiteralPath $PayloadPath -Raw | ConvertFrom-Json
$word = [Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application')
$document = $null
for ($index = 1; $index -le $word.Documents.Count; $index++) {
	$candidate = $word.Documents.Item($index)
	$candidateFullName = $null
	try {
		$candidateFullName = [string] $candidate.FullName
	} catch {
	}
	if ($candidateFullName -eq $payload.fullName -or $candidate.Name -eq $payload.fileName) {
		$document = $candidate
		break
	}
}
if ($null -eq $document) {
	throw "The open Word document was not found."
}
if ($payload.selectResult) {
	$word.Visible = $true
}
$document.Activate()
if ($payload.selectResult) {
	try {
		$word.Activate()
	} catch {
	}
	try {
		$shell = New-Object -ComObject WScript.Shell
		$shell.AppActivate($word.Caption) | Out-Null
	} catch {
	}
}
$selection = $word.Selection
$find = $selection.Find
$find.ClearFormatting()
$find.Forward = $true
$find.Wrap = 0
$find.MatchCase = $true
$locations = @{}
foreach ($request in $payload.requests) {
	$selection.HomeKey(6) | Out-Null
	$find.Text = [string] $request.text
	$foundCount = 0
	$foundAtRequestedLocation = $false
	if ($payload.selectResult -and $null -ne $request.page) {
		try {
			$targetPage = [int] $request.page
			$targetLine = $null
			if ($null -ne $request.visualLine) {
				$targetLine = [int] $request.visualLine
			}
			$pageRange = $document.GoTo(1, 1, $targetPage)
			$pageRange.Select()
			while ($find.Execute()) {
				$currentPage = $selection.Information(3)
				$currentLine = $selection.Information(10)
				if ($currentPage -gt $targetPage) {
					break
				}
				if ($currentPage -eq $targetPage -and ($null -eq $targetLine -or $currentLine -ge $targetLine)) {
					$foundAtRequestedLocation = $true
					break
				}
				$selection.Collapse(0)
			}
		} catch {
			$selection.HomeKey(6) | Out-Null
		}
	}
	if (-not $foundAtRequestedLocation) {
		$selection.HomeKey(6) | Out-Null
		while ($foundCount -lt [int] $request.occurrence) {
			if (-not $find.Execute()) {
				break
			}
			$foundCount += 1
			if ($foundCount -lt [int] $request.occurrence) {
				$selection.Collapse(0)
			}
		}
	}
	if ($foundAtRequestedLocation -or $foundCount -eq [int] $request.occurrence) {
		$locations[[string] $request.index] = @($selection.Information(3), $selection.Information(10))
		if (-not $payload.selectResult) {
			$selection.Collapse(0)
		}
	}
}
$locations | ConvertTo-Json -Compress
'''


def collect_docx_visual_locations(word, results, extracted_text, on_result=None, should_continue=None):
	# Walk the document forward once, mapping each result to the page and visual
	# line Word reports. Results arrive in document order, so for a given match
	# string the occurrences are reached in ascending order without restarting
	# from the top of the document for every match. This turns a per-match
	# O(n^2) search into a single O(n) forward pass. MatchCase keeps Word's
	# stepping aligned with the case-sensitive occurrence count below.
	#
	# on_result(local_index, location) is called for every result as it is
	# resolved (location is None when Word could not reach it), letting the caller
	# stream progress to the UI. should_continue() lets the caller abort the pass
	# early, e.g. when the search has been superseded.
	selection = word.Selection
	find = selection.Find
	find.ClearFormatting()
	find.Forward = True
	find.Wrap = 0
	find.MatchCase = True
	locations = {}
	current_text = None
	found_count = 0
	for index, result in enumerate(results):
		if should_continue is not None and not should_continue():
			break
		matched_text = extracted_text[result.start:result.end]
		if not matched_text:
			if on_result is not None:
				on_result(index, None)
			continue
		occurrence = extracted_text[:result.start].count(matched_text) + 1
		if matched_text != current_text:
			selection.HomeKey(Unit=6)
			find.Text = matched_text
			current_text = matched_text
			found_count = 0
		while found_count < occurrence:
			if not find.Execute():
				break
			found_count += 1
			if found_count < occurrence:
				selection.Collapse(0)
		if found_count < occurrence:
			if on_result is not None:
				on_result(index, None)
			continue
		location = (selection.Information(3), selection.Information(10))
		locations[index] = location
		selection.Collapse(0)
		if on_result is not None:
			on_result(index, location)
	return locations


def batched_items(items, size):
	for start in range(0, len(items), size):
		yield items[start:start + size]


def open_result_file(result, extracted_text=None):
	log_info("Text Finder opening original file with a %s extension.", result.path.suffix.lower() or "no-extension")
	if result.path.suffix.lower() == ".docx":
		if extracted_text is None:
			try:
				extracted_text = extract_text(result.path).text
			except Exception:
				log_exception("Text Finder could not extract DOCX text before opening in Word.")
				open_file_or_select(result.path)
				return result
		updated_result = open_docx_result_in_word(result, extracted_text)
		if updated_result is not None:
			return updated_result
		ui.message(_("Could not open this DOCX in Word. Opened the file normally."))
	open_file_or_select(result.path)
	return result


def go_to_word_result(result, extracted_text):
	try:
		locations = get_open_word_visual_locations(result.path, [result], extracted_text, select_result=True)
		if locations and 0 in locations:
			page, visual_line = locations[0]
			schedule_window_foreground(result.path)
			ui.message(_("Moved to page {page}, visual line {line}.").format(page=page, line=visual_line))
			return replace(result, page=page, line=visual_line, column=0, location_unit="Visual line", word_pending=False)
		ui.message(_("Could not move to this result in the open Word document."))
		return result
	except Exception:
		log_exception("Text Finder could not move to the Word result.")
		ui.message(_("Could not move to this result in Word."))
		return None


def open_docx_result_in_word(result, extracted_text):
	try:
		os.startfile(str(result.path))
		schedule_window_foreground(result.path)
		for _attempt in range(12):
			time.sleep(0.5)
			locations = get_open_word_visual_locations(result.path, [result], extracted_text, select_result=True)
			if locations and 0 in locations:
				page, visual_line = locations[0]
				schedule_window_foreground(result.path)
				ui.message(_("Opened in Word at page {page}, visual line {line}.").format(page=page, line=visual_line))
				return replace(result, page=page, line=visual_line, column=0, location_unit="Visual line", word_pending=False)
		ui.message(_("Opened in Word, but Text Finder could not move to the exact result."))
		return result
	except Exception:
		log_exception("Text Finder could not open DOCX result in Word.")
		return None


def get_word_application(new_instance=False):
	try:
		import win32com.client

		if new_instance and hasattr(win32com.client, "DispatchEx"):
			return win32com.client.DispatchEx("Word.Application")
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
		schedule_window_foreground(path)
	except Exception:
		subprocess.Popen(["explorer.exe", "/select,", str(path)])
		schedule_window_foreground(path)


def schedule_window_foreground(path):
	timer = threading.Timer(0.8, bring_window_for_path_to_front, args=(Path(path),))
	timer.daemon = True
	timer.start()


def activate_word_window(word, document, path):
	try:
		word.Visible = True
	except Exception:
		pass
	for target in (document, getattr(word, "ActiveWindow", None), word):
		if target is None:
			continue
		try:
			target.Activate()
		except Exception:
			pass
	schedule_window_foreground(path)


def bring_window_for_path_to_front(path):
	try:
		file_name = path.name.lower()
		if not file_name:
			return False
		user32 = ctypes.windll.user32
		matches = []

		def enum_window(hwnd, _lparam):
			if not user32.IsWindowVisible(hwnd):
				return True
			length = user32.GetWindowTextLengthW(hwnd)
			if length <= 0:
				return True
			buffer = ctypes.create_unicode_buffer(length + 1)
			user32.GetWindowTextW(hwnd, buffer, length + 1)
			if file_name in buffer.value.lower():
				matches.append(hwnd)
				return False
			return True

		enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(enum_window)
		user32.EnumWindows(enum_proc, 0)
		if not matches:
			return False
		hwnd = matches[0]
		user32.ShowWindow(hwnd, 9)
		user32.SetForegroundWindow(hwnd)
		return True
	except Exception:
		log_exception("Text Finder could not bring the opened file window to the front.")
		return False


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
		self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
		self.reportCtrl.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
		copyButton.Bind(wx.EVT_BUTTON, self.on_copy)
		closeButton.Bind(wx.EVT_BUTTON, lambda evt: self.Destroy())

	def on_char_hook(self, evt):
		if evt.GetKeyCode() == wx.WXK_ESCAPE:
			self.Destroy()
			return
		evt.Skip()

	def on_copy(self, evt):
		if wx.TheClipboard.Open():
			wx.TheClipboard.SetData(wx.TextDataObject(self.report))
			wx.TheClipboard.Close()
			ui.message(_("Search statistics copied to clipboard."))


def format_result_for_list(result):
	if get_setting("showFullPath"):
		return _("{file}, {location}, {path}, preview: {preview}").format(
			file=result.path.name,
			location=result.format_location(),
			path=result.path,
			preview=result.preview,
		)
	return _("{file}, {location}, preview: {preview}").format(
		file=result.path.name,
		location=result.format_location(),
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
