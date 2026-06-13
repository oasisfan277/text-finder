# Contributing

Thank you for helping improve Text Finder.

## Project Principles

- Keep all search and text extraction local.
- Do not add telemetry, analytics, online processing, or cloud services.
- Preserve accessibility for speech, braille, keyboard navigation, and review.
- Do not invent page numbers when reliable page information is unavailable.
- Keep exact fragment search literal.

## Testing

Run the local checks before submitting a pull request:

```powershell
python -m compileall addon tests
python -c "import tests.test_search_engine as t; [getattr(t, name)() for name in dir(t) if name.startswith('test_')]; print('search tests passed')"
```

