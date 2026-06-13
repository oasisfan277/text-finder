# Text Finder

Text Finder is an NVDA add-on for searching files containing text in the current folder, a selected folder, or the parent folder of a focused file.

The add-on is designed for precise local searching. It can search for exact fragments, exact whole words, punctuation, repeated spaces, tabs, and line breaks. Results are presented in an accessible dialog with file, location, preview text, and page number when reliable page information is available. Text files use line and column. Word-style documents use Open Result for the exact position because Word visual lines are layout-dependent and are not stable document data.

## Privacy

Text Finder performs all searching locally on the user's computer.

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

Text Finder targets files with extractable text, including:

- TXT, LOG, MD, CSV, INI
- JSON, XML, HTML, HTM
- CSS, JavaScript, Python
- DOCX
- RTF
- ODT
- XLSX (modern Excel workbooks)
- PPTX (modern PowerPoint presentations)
- Text-based PDF files when a local PDF text extraction library is available

Excel and PowerPoint support covers the modern .xlsx and .pptx formats. The older binary .xls and .ppt formats are not searched. Image-only or scanned PDFs are not OCR'd.

## Search Modes

- Exact fragment search
- Exact whole-word search
- Case-sensitive or case-insensitive search
- Include subfolders
- Page number reporting when reliable page information is available

Exact fragment search matches the query literally, including punctuation, symbols, spaces, repeated spaces, tabs, line breaks, blank lines, partial words, and parts of file paths.

The file types to search are chosen in the NVDA settings panel rather than in the search dialog. See NVDA Settings below.

## NVDA Settings

Text Finder adds an NVDA settings panel with these options:

- Allow direct entry of tabs and line breaks in the search field.
- Announce invisible characters while typing.
- Report page numbers when available.
- Show the full file path in search results.
- Search all supported file types, or only the file types you choose.

Standard keyboard navigation remains the default. Advanced direct entry can be enabled by users who need to search for literal tabs or line breaks.

By default, search results read only the document name. Enable "Show the full file path in search results" to include the complete path for each result.

### Choosing Which File Types To Search

By default, "Search all supported file types" is enabled, so every supported type is searched. To narrow a search, clear that checkbox and tick only the file types you want in the "File types to search" list. If you clear the checkbox but tick nothing, all supported types are searched so a search is never silently empty. The choice persists across NVDA sessions.

## Results And Opening

Use Open Result, or press Enter on a selected result, to open the extracted document text at the exact match. Use Open File to open the original file.

For DOCX files, the add-on asks Microsoft Word for live page and visual line numbers after the search completes. Results are revealed straight away, and the Word page and visual line numbers are filled in afterwards in the background, updating each result in place as Word reports it. While a Word result is still loading its numbers it reads as "Word location loading". If Word cannot supply the numbers, the result falls back to the Open Result position so the list is never left stuck.

## Search Statistics

After each search, the results dialog offers a Search Statistics report. It lists the search folder, search mode, duration, number of matches, number of searched files, unsupported files, unreadable files, and files without extractable text.

## Remembered Search Options

The search mode (Exact fragment or Exact whole word), case sensitivity, Include subfolders, and page-number reporting are remembered each time you search. The next time you open Text Finder, your last choices are restored. The file types to search and all other settings are kept in the settings panel. These choices persist across NVDA sessions.

## What NVDA Announces During a Search

The spoken workflow is intentionally explicit so it can be followed end to end:

1. Activating the command announces "Text Finder starting." When the dialog opens it announces "Text Finder opened. Search folder:" followed by the folder. If no folder can be detected, it asks you to open a folder or focus a file first.
2. As you type, the read-only preview updates. With invisible-character announcements enabled, spaces, tabs, and line breaks are announced as you enter them.
3. Activating Search announces "Searching."
4. When the search finishes, focus moves to the results list, the first result is read, and the search summary is announced.
5. When the results include Word documents, NVDA announces that it is getting Word page and visual line numbers in the background, then announces how many results were updated once the numbers are ready.
6. Each result reads as document name, location, and a matching-text preview. The full file path is included only when "Show the full file path in search results" is enabled.
7. Open Result, or Enter on a result, announces that the result opened at the exact match or at the reported location. Open File on a Word document announces the page and visual line that Word reports.
8. Search Statistics opens a report you can read or copy to the clipboard.

## Project Status

This repository contains the add-on and its core local search engine. It is being tested before NVDA Add-on Store submission.


## Building The Add-on

Build a local `.nvda-addon` package with:

```powershell
python scripts/package_addon.py
```

The package is written to the `dist` folder.
