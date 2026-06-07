# Folder Text Finder

Folder Text Finder is an NVDA add-on for searching files containing text in the current folder, a selected folder, or the parent folder of a focused file.

The add-on is designed for precise local searching. It can search for exact fragments, exact whole words, punctuation, repeated spaces, tabs, and line breaks. Results are presented in an accessible dialog with file, line, column, preview text, and page number when reliable page information is available.

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

Standard keyboard navigation remains the default. Advanced direct entry can be enabled by users who need to search for literal tabs or line breaks.

## Search Statistics

After each search, the results dialog offers a Search Statistics report. It lists the search folder, search mode, duration, number of matches, number of searched files, unsupported files, unreadable files, and files without extractable text.

## Project Status

This repository contains the initial add-on scaffold and core local search engine. It is not yet ready for NVDA Add-on Store submission.


## Building The Add-on

Build a local `.nvda-addon` package with:

```powershell
python scripts/package_addon.py
```

The package is written to the `dist` folder.
