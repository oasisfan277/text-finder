# Text Finder

Text Finder searches files containing text in the current folder, a selected folder, a selected file, or a supported Office document that is currently open.

## Privacy and Security

All searches are conducted locally on your computer. No files, search terms, document contents, file names, or statistics are uploaded or processed online. The add-on does not use cloud services, online APIs, telemetry, or analytics.

The Search Statistics report is generated locally and remains available only until another search is started or the add-on is closed.

## Command

Press `NVDA+Alt+F` to open Text Finder from File Explorer, a selected file, or a supported open Office document. The command can be changed in NVDA's Input Gestures dialog.

## Searching

The search field accepts ordinary text. Exact fragment search matches what you enter literally, including punctuation, repeated spaces, tabs, and line breaks.

The search mode choices are Exact fragment and Exact whole word. Exact fragment is selected by default.

By default, the search field uses standard keyboard navigation:

- Space inserts a space.
- Tab moves to the next control.
- Shift+Tab moves to the previous control.
- Enter starts the search.

An advanced setting allows direct entry of tabs and line breaks in the search field.

## Settings

Text Finder adds an NVDA settings panel with these options:

- Allow direct entry of tabs and line breaks in the search field.
- Announce invisible characters while typing.
- Report page numbers when available.
- Show the full file path in search results.
- Search all supported file types, or only the file types you choose. Each file type item says Selected or Not selected for screen reader clarity.

### Choosing Which File Types To Search

The file types to search are chosen in the settings panel, not in the search dialog. By default, "Search all supported file types" is enabled, so every type Text Finder understands is searched. Each item in the file type list includes "Selected" or "Not selected" in its name.

To narrow a search, clear "Search all supported file types" and tick only the file types you want in the "File types to search" list. If you clear the checkbox but tick nothing, Text Finder searches all supported types so a search is never silently empty. Your choice is remembered across NVDA sessions.

The search dialog also contains a read-only preview of the search text. Spaces, tabs, line breaks, and carriage returns are shown in a readable form so the exact search text can be checked before searching.

## Results

Results include the document name, location, matching text preview, and page number when reliable page information is available. By default the full file path is not read; enable "Show the full file path in search results" in the settings to include it. Text files use line and column. Word-style documents use Open Result for the exact position because Word visual lines are layout-dependent and are not stable document data.

Search results for prose try to show the whole sentence containing the match. If that sentence is very short, the next sentence is included as well.

Use Open Result, or press Enter on a selected result, to open the extracted document text at the exact match. Use Open File to open the original file.

For DOCX files, the add-on asks Microsoft Word for live page and visual line numbers after the search completes. Results are revealed straight away, and the Word page and visual line numbers are filled in afterwards in the background, updating each result in place as Word reports it. While a Word result is still loading its numbers it reads as "Word location loading". If Word cannot supply the numbers, the result falls back to the Open Result position so the list is never left stuck.

Page numbers are reported when available. The add-on does not estimate or invent page numbers.

## Remembered Search Options

The search mode, case sensitivity, Include subfolders, and page-number reporting are remembered each time you search and restored the next time you open Text Finder. The file types to search and all other settings are kept in the settings panel. These choices persist across NVDA sessions.

## What NVDA Announces During a Search

1. Activating the command announces "Text Finder starting", then "Text Finder opened. Search target:" followed by the file or folder. If no target is detected, it asks you to open a folder, focus a file, or open a supported Office document first.
2. As you type, the read-only preview updates. With invisible-character announcements enabled, spaces, tabs, and line breaks are announced as you enter them.
3. Activating Search announces "Searching."
4. When the search finishes, focus moves to the results list, the first result is read, and the search summary is announced.
5. When the results include Word documents, NVDA announces that it is getting Word page and visual line numbers in the background, then announces how many results were updated once the numbers are ready.
6. Each result reads as document name, location, and a matching-text preview. The full file path is included only when "Show the full file path in search results" is enabled.
7. Open Result, or Enter on a result, announces that the result opened at the exact match or at the reported location. Open File on a Word document announces the page and visual line that Word reports.
8. Search Statistics opens a report you can read or copy to the clipboard.

## Supported Files

Text Finder searches common files with extractable text, including plain text, source code, markup files, DOCX, RTF, ODT, Excel workbooks (.xlsx), PowerPoint presentations (.pptx), and text-based PDF documents when local PDF text extraction support is available.

Excel and PowerPoint support covers the modern .xlsx and .pptx formats. The older binary .xls and .ppt formats are not searched.

Image-only or scanned PDFs are not OCR'd.

## Search Statistics

After a search, use Search Statistics to review what was searched, skipped, unsupported, unreadable, or found to contain no extractable text.
