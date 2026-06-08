# Changelog

## 0.2.2

- Read only the document name in search results by default instead of the full file path.
- Added a setting to show the full file path in search results for users who want it.

## 0.2.1

- Revealed search results immediately and filled Word page and visual line numbers in the background, updating each result in place, instead of holding every result until the whole Word lookup finished.
- Showed "Word location loading" for Word results until their numbers arrive, then updated them in place, instead of announcing the exact-position placeholder while waiting.
- Fell back to the Open Result position for any Word result that Word did not report, so results never stay stuck on loading.
- Greatly sped up the Word lookup by reusing a single hidden Word instance for the whole search and walking each document once instead of restarting the search from the top of the document for every match.

## 0.2.0

- Held the results announcement for searches that contain DOCX files until the background Word page and visual line numbers finish loading, then revealed and announced the results once, so results are not announced twice with incomplete locations.
- Revealed the results even when the background Word lookup fails, so the results list is never left silent.
- Remembered the search mode, case sensitivity, include-subfolders choice, file name filters, and page-number reporting between searches and NVDA sessions.
- Added workflow logging for each search stage so the spoken workflow can be reviewed in the NVDA log without recording search text or document contents.
- Added a step-by-step description of what NVDA announces during a search.

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
- Added Enter-to-open result text with the caret placed on the exact match.
- Added separate Open File and Open Result actions for search results.
- Changed DOCX and ODT result locations to point users to Open Result instead of showing misleading line, paragraph, or text block numbers.
- Added DOCX support that asks Microsoft Word for the live page and visual line when opening a selected result.
- Updated selected DOCX results to announce and display Word page and visual line after Open File succeeds.
- Added hidden background Word lookup to fill DOCX search results with page and visual line numbers after a search without showing Word.
- Removed automatic Word lookups during search so Word only opens the one selected result when the user chooses Open File.
- Fixed Word automation startup on systems where the COM library rejects the dynamic COM argument.
- Added a local package builder for creating `.nvda-addon` files.
- Added GitHub Actions package artifact upload.
- Added privacy-focused documentation.
