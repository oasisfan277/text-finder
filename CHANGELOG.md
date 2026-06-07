# Changelog

## 0.1.0

- Initial project scaffold.
- Added local search engine with exact fragment and exact whole-word matching.
- Exact whole-word matching no longer matches apostrophe suffixes such as sister's.
- Added local extractors for plain text, HTML, DOCX, RTF, ODT, and optional text-based PDF extraction.
- Added accessible NVDA global plugin dialog scaffold.
- Added NVDA settings for direct tab/newline entry, invisible character announcements, and page number reporting.
- Improved current File Explorer folder detection using the Windows Shell application when available.
- Allowed folder detection to use the parent folder of a focused file path.
- Added readable invisible-character preview text for the search query.
- Added explicit Exact fragment and Exact whole word search-mode choices.
- Added sentence excerpts for prose search results.
- Added a local package builder for creating `.nvda-addon` files.
- Added GitHub Actions package artifact upload.
- Added privacy-focused documentation.
