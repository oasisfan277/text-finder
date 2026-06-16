# Changelog

## 0.4.12

- Fill in page and visual line numbers for far more results. The automatic lookup was capped at the first 50 Word matches as a workaround for the old slow lookup; now that it is a single fast pass, the cap is raised to 2000 so whole-document searches (hundreds of matches) get located instead of stopping part way down the list.

## 0.4.11

- Fix page and visual line numbers staying blank ("Exact position in Open Result") when the document is already open in Word: the lookup now reads from the running Word instance instead of trying to open a second, hidden copy, which OneDrive and Word refuse with a "file in use by another application" error. The read uses a background Range, so it never moves the cursor or scrolls the open document.

## 0.4.10

- Fix Word page and visual line numbers never appearing for documents with many matches: enrichment now walks each document in a single forward pass in a hidden Word instance instead of restarting Word's search from the top for every batch of 10 (and no longer launches a PowerShell process per batch), so large books resolve in seconds instead of stalling.
- Speed up Go to Search Result indirectly: because page anchors now fill in reliably, the jump uses the direct page anchor instead of falling back to stepping through hundreds of matches.

## 0.4.9

- Keep Go to Search Result on the intended Word page by searching only within the reported page instead of moving by visual-line counts.
- Close the Text Finder search dialog after a successful Word result jump.
- Limit automatic Word page and visual line lookup to the first 50 Word results to reduce sluggishness in large documents.

## 0.4.8

- Speed up Go to Search Result by jumping directly to the reported Word page and visual line when they are already known.

## 0.4.7

- Use the already-reported Word page and visual line as the anchor when going to a Word result, avoiding wrong jumps in documents with many repeated matches.
- Stop background Word location lookup without rewriting every pending result, reducing sluggishness after Go to Search Result.

## 0.4.6

- Show Word page and visual line lookup progress inside the main search dialog instead of announcing each batch separately.
- For single Word-document searches, show Go to Search Result without the Open File or Open Result buttons.
- Stop background Word page and visual line lookup when the user goes to a result.

## 0.4.5

- Process Word page and visual line lookup in batches of 10 results, so large documents can update result locations progressively instead of failing all at once.

## 0.4.4

- Hide the Include subfolders checkbox when Text Finder is searching inside a single file.

## 0.4.3

- Open Word results through Windows' normal file opening route first, then attach to Word and move to the result, preserving Word's usual AutoSave and collaboration behavior more reliably.
- Match already-open Word documents by full path before falling back to the document name.

## 0.4.2

- Open Word results in editable mode when the user chooses Open File, while keeping background Word location checks read-only.
- Improved Word foreground activation when opening or moving to a search result.

## 0.4.1

- Hid the Go to Search Result button during folder searches, where Open File already opens the selected result.
- Brought opened file windows forward after using Open File so users do not need to hunt through several open windows.

## 0.4.0

- Reset Text Finder to a Word-first design based on the faster 0.3.13 behavior, with automatic Word page and visual line lookup in results.
- Removed PDF support from the default add-on path to keep searches fast and predictable.

## 0.3.33

- Restored PDFs to all-file folder searches while keeping open-PDF detection out of startup.
- Restored automatic Word page and visual line lookup for the first 50 Word results, with a More Word Info button for later batches.

## 0.3.32

- Added a Get More Info action for a selected Word result, so page and visual line lookup runs only for that one result when requested.

## 0.3.31

- Kept broad folder searches responsive by excluding PDFs from "all supported file types"; select PDF documents explicitly to search PDFs.

## 0.3.30

- Prevented large Word folder searches from freezing NVDA by skipping automatic page and visual line lookup when there are more than 50 Word results.

## 0.3.29

- Fixed PDF searches returning no results on NVDA, whose bundled Python omits the `secrets` and `xml.dom` modules that the PDF reader needs; these are now provided with the add-on.
- Sped up opening Text Finder by only scanning for an open PDF document when PDF is one of the file types being searched.

## 0.3.28

- Fixed single-file searches turning off the saved include-subfolders option for later folder searches.

## 0.3.27

- Clarified folder search summaries by reporting both searched file types and match counts by file type.

## 0.3.26

- Added match counts by file type to search summaries and used Windows recent PDFs as another fallback for browser-opened PDF detection.

## 0.3.25

- Defaulted folder searches to include subfolders and matched Chrome PDF titles without a `.pdf` extension to local PDF files.

## 0.3.24

- Fixed a PDF search crash caused by Unicode offset changes and cancelled running searches when Text Finder is closed.

## 0.3.23

- Made the active file-type filter visible in the search dialog and reset the close button to a standard Escape-friendly dialog button.

## 0.3.22

- Added foreground-window UI scanning for browser-opened PDFs and made short exact-fragment searches match through punctuation or spacing.

## 0.3.21

- Prioritized open document detection before folder fallback and made Escape close the main Text Finder dialog more consistently.

## 0.3.20

- Bundled the PDF text reader and broadened open-PDF detection to find PDF paths from accessible text, file URLs, and running viewer process data.

## 0.3.19

- Detected open PDF files in common PDF viewers and browsers, including Chrome, so PDF documents can be searched when already open.

## 0.3.18

- Added an off-by-default setting to close Text Finder automatically after Go to Search Result succeeds.

## 0.3.17

- Reused an already-open Notepad window when jumping to a search result in a text file, opening Notepad only as a fallback.

## 0.3.16

- Explicitly hid folder and open-result controls in the search dialog when searching inside a single file.

## 0.3.15

- Improved Notepad single-file detection, simplified single-file search buttons further, and made Go to Search Result wait for Notepad before jumping to the line.

## 0.3.14

- Added Go to Search Result support for Notepad-friendly files and PDFs, and simplified the search dialog during single-file searches.

## 0.3.13

- Simplified statistics for single-file searches and made search dialog shortcut keys unique.

## 0.3.12

- Added Escape to close Text Finder windows, a Go to Search Result button for Word results, and moved selected file types to the top of the settings list when Search all supported file types is off.

## 0.3.11

- Used the already-open Word document for page and visual line lookup before falling back to opening a separate read-only document.

## 0.3.10

- Opened Word documents read-only for page and visual line lookup, so results from an already-open document can still get Word page and visual line numbers.

## 0.3.9

- Updated the locked Word document fallback to open DOCX files with shared read access, so files already open in Word can still be searched.

## 0.3.8

- Updated the locked Word document fallback to call PowerShell by its full Windows path when NVDA cannot find it from the environment.

## 0.3.7

- Added a fallback for Word documents that Windows reports as permission denied while they are open in Word.

## 0.3.6

- Normalized single-file search targets before searching and added clearer diagnostics for searches that return no results.

## 0.3.5

- Improved open Word document detection when NVDA cannot use direct Word automation by matching the active Word document name to the selected or visible file in File Explorer.

## 0.3.4

- Improved open Microsoft Word document detection by attaching to the running Word instance instead of relying only on NVDA's foreground app name.

## 0.3.3

- Fixed the file type settings list so turning off Search all supported file types clears the list, letting users choose only the file types they want.

## 0.3.2

- Added cautious plain-text fallback for specifically targeted unknown-extension files, so files that open as text in Notepad can be searched without scanning binary files in folder searches.
- Kept binary-looking unknown files skipped to avoid trying to search music, pictures, and other non-text files.

## 0.3.1

- Made file-type choices in the settings panel announce their selected or not selected state in the item text for screen reader users.
- Added search targeting for a focused file, selected file, or supported open Office document instead of only searching folders.

## 0.3.0

- Completed the rename to Text Finder across the add-on ID, package name, plugin folder, metadata, and documentation.
- Added searching of modern Excel workbooks (.xlsx) and PowerPoint presentations (.pptx), read locally without Microsoft Office. The older binary .xls and .ppt formats are not searched.
- Moved the file-type choice out of the search dialog and into the NVDA settings panel, where you can search all supported file types or tick only the specific types you want. The choice persists across NVDA sessions.

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
