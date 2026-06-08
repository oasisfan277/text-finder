# Folder Text Finder

Folder Text Finder is an NVDA add-on for searching files containing text in the current folder, a selected folder, or the parent folder of a focused file.

The add-on is designed for precise local searching. It can search for exact fragments, exact whole words, punctuation, repeated spaces, tabs, and line breaks. Results are presented in an accessible dialog with file, location, preview text, and page number when reliable page information is available. Text files use line and column. Word-style documents use Open Result for the exact position because Word visual lines are layout-dependent and are not stable document data.

## Privacy

Folder Text Finder performs all searching locally on the user's computer.

- No file contents are uploaded.
- No search queries are transmitted over the Internet.
- No cloud services or online APIs are used.
- No telemetry or usage statistics are collected.
- No document contents are stored after the search completes.

All text extraction and searching is performed on the local machine.

## Default Gesture

The default gesture is:

`NVDA+Alt+F`

The gesture can be changed from NVDA's Input Gestures dialog.

## Supported Files

The first version targets files with extractable text, including:

- TXT, LOG, MD, CSV, INI
- JSON, XML, HTML, HTM
- CSS, JavaScript, Python
- DOCX
- RTF
- ODT
- Text-based PDF files when a local PDF text extraction library is available

Image-only or scanned PDFs are not OCR'd.

## Search Modes

- Exact fragment search
- Exact whole-word search
- Case-sensitive or case-insensitive search
- Include subfolders
- File type filtering
- Page number reporting when reliable page information is available

Exact fragment search matches the query literally, including punctuation, symbols, spaces, repeated spaces, tabs, line breaks, blank lines, partial words, and parts of file paths.

## NVDA Settings

Folder Text Finder adds an NVDA settings panel with these options:

- Allow direct entry of tabs and line breaks in the search field.
- Announce invisible characters while typing.
- Report page numbers when available.
- Show the full file path in search results.

Standard keyboard navigation remains the default. Advanced direct entry can be enabled by users who need to search for literal tabs or line breaks.

By default, search results read only the document name. Enable "Show the full file path in search results" to include the complete path for each result.

## Search Statistics

Use Open Result, or press Enter on a selected result, to open the extracted document text at the exact match. Use Open File to open the original file.

For DOCX files, the add-on asks Microsoft Word for live page and visual line numbers after the search completes. While those numbers load, the results are held back instead of being announced with incomplete locations. NVDA reports that it is getting Word page and visual line numbers, and then reveals the finished results in one pass. If Word cannot supply the numbers, the results are still revealed using the Open Result position so the list is never left silent.

After each search, the results dialog offers a Search Statistics report. It lists the search folder, search mode, duration, number of matches, number of searched files, unsupported files, unreadable files, and files without extractable text.

## Remembered Search Options

The search mode (Exact fragment or Exact whole word), case sensitivity, Include subfolders, file name filters, and page-number reporting are remembered each time you search. The next time you open Folder Text Finder, your last choices are restored. The settings persist across NVDA sessions.

## What NVDA Announces During a Search

The spoken workflow is intentionally explicit so it can be followed end to end:

1. Activating the command announces "Folder Text Finder starting." When the dialog opens it announces "Folder Text Finder opened. Search folder:" followed by the folder. If no folder can be detected, it asks you to open a folder or focus a file first.
2. As you type, the read-only preview updates. With invisible-character announcements enabled, spaces, tabs, and line breaks are announced as you enter them.
3. Activating Search announces "Searching."
4. When the search finishes and there are no Word documents in the results, focus moves to the results list, the first result is read, and the search summary is announced.
5. When the results include Word documents, NVDA announces "Getting Word page and visual line numbers. Please wait." The results are revealed only after the numbers load, prefixed with how many results were updated, followed by the search summary. If the Word lookup fails, the failure is announced and the results are still revealed.
6. Each result reads as document name, location, and a matching-text preview. The full file path is included only when "Show the full file path in search results" is enabled.
7. Open Result, or Enter on a result, announces that the result opened at the exact match or at the reported location. Open File on a Word document announces the page and visual line that Word reports.
8. Search Statistics opens a report you can read or copy to the clipboard.

## Project Status

This repository contains the initial add-on scaffold and core local search engine. It is not yet ready for NVDA Add-on Store submission.


## Building The Add-on

Build a local `.nvda-addon` package with:

```powershell
python scripts/package_addon.py
```

The package is written to the `dist` folder.
