"""Version sort keys: strict for known-good strings, loose for strings from outside."""

from __future__ import annotations

import pytest
from _lib.versions import loose_version_key, version_key


def test_strict_key_orders_numerically_not_alphabetically() -> None:
    assert sorted(["2.1.9", "2.1.21", "2.0.77"], key=version_key) == ["2.0.77", "2.1.9", "2.1.21"]


def test_strict_key_rejects_a_suffix() -> None:
    with pytest.raises(ValueError):
        version_key("2.1.21-beta")


def test_loose_key_tolerates_suffixes_and_orders_them_after_the_plain_release_parts() -> None:
    assert loose_version_key("2.1.21-beta") == (2, 1, 21, 0)
    assert sorted(["1.10.0", "1.9.3"], key=loose_version_key) == ["1.9.3", "1.10.0"]
