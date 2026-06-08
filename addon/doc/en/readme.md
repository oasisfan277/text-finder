# Folder Text Finder

Folder Text Finder searches files containing text in the current folder, a selected folder, or the parent folder of a focused file.

## Privacy and Security

All searches are conducted locally on your computer. No files, search terms, document contents, file names, or statistics are uploaded or processed online. The add-on does not use cloud services, online APIs, telemetry, or analytics.

The Search Statistics report is generated locally and remains available only until another search is started or the add-on is closed.

## Command

Press `NVDA+Alt+F` to open Folder Text Finder from File Explorer. The command can be changed in NVDA's Input Gestures dialog.

## Searching

The search field accepts ordinary text. Exact fragment search matches what you enter literally, including punctuation, repeated spaces, tabs, and line breaks.

The search mode choices are Exact fragment and Exact whole word. Exact fragment is selected by default.

By default, the search field uses standard keyboard navigation:

- Space inserts a space.
- Tab moves to the next control.
- Shift+Tab moves to the previous control.
- Enter starts the search.

An advanced setting will allow direct entry of tabs and line breaks in the search field.

## Settings

Folder Text Finder adds an NVDA settings panel with these options:

- Allow direct entry of tabs and line breaks in the search field.
- Announce invisible characters while typing.
- Report page numbers when available.

The search dialog also contains a read-only preview of the search text. Spaces, tabs, line breaks, and carriage returns are shown in a readable form so the exact search text can be checked before searching.

## Results

Results include the file name, full path, location, matching text preview, and page number when reliable page information is available. Text files use line and column. Word-style documents use Open Result for the exact position because Word visual lines are layout-dependent and are not stable document data.

Search results for prose try to show the whole sentence containing the match. If that sentence is very short, the next sentence is included as well.

Use Open Result, or press Enter on a selected result, to open the extracted document text at the exact match. Use Open File to open the original file.

For DOCX files, the add-on asks Microsoft Word for live page and visual line numbers after the search completes. While those numbers load, the results are held back instead of being announced with incomplete locations. NVDA reports that it is getting Word page and visual line numbers, and then reveals the finished results in one pass. If Word cannot supply the numbers, the results are still revealed using the Open Result position so the list is never left silent.

Page numbers are reported when available. The add-on does not estimate or invent page numbers.

## Remembered Search Options

The search mode, case sensitivity, Include subfolders, file name filters, and page-number reporting are remembered each time you search and restored the next time you open Folder Text Finder. The settings persist across NVDA sessions.

## What NVDA Announces During a Search

1. Activating the command announces "Folder Text Finder starting", then "Folder Text Finder opened. Search folder:" followed by the folder. If no folder is detected, it asks you to open a folder or focus a file first.
2. As you type, the read-only preview updates. With invisible-character announcements enabled, spaces, tabs, and line breaks are announced as you enter them.
3. Activating Search announces "Searching."
4. When the results contain no Word documents, focus moves to the results list, the first result is read, and the search summary is announced.
5. When the results include Word documents, NVDA announces "Getting Word page and visual line numbers. Please wait." The results are revealed only after the numbers load, prefixed with how many results were updated, followed by the search summary. If the Word lookup fails, the failure is announced and the results are still revealed.
6. Each result reads as file name, location, full path, and a matching-text preview.
7. Open Result, or Enter on a result, announces that the result opened at the exact match or at the reported location. Open File on a Word document announces the page and visual line that Word reports.
8. Search Statistics opens a report you can read or copy to the clipboard.

## Supported Files

Folder Text Finder searches common files with extractable text, including plain text, source code, markup files, DOCX, RTF, ODT, and text-based PDF documents when local PDF text extraction support is available.

Image-only or scanned PDFs are not OCR'd.

## Search Statistics

After a search, use Search Statistics to review what was searched, skipped, unsupported, unreadable, or found to contain no extractable text.
