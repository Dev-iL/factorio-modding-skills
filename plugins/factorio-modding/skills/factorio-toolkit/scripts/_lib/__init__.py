"""Shared helpers for the factorio-toolkit scripts.

Scripts live one directory up and are run as `uv run --script <script>`; uv puts the script's
directory first on `sys.path`, so they import this package as `_lib`.
"""
