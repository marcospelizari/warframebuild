import lzma

import pytest

from app.data.sources.de_export import EXPORTS, IndexError_, decode_index
from tests.data.conftest import FIXTURE_RAW


def test_decodes_index_with_broken_end_marker() -> None:
    entries = decode_index((FIXTURE_RAW / "de/index_en.txt.lzma").read_bytes())
    for name in EXPORTS:
        assert entries[name].startswith(f"{name}!00_")


def test_rejects_truncated_index() -> None:
    raw = (FIXTURE_RAW / "de/index_en.txt.lzma").read_bytes()
    with pytest.raises(IndexError_):
        decode_index(raw[: len(raw) // 2])


def test_rejects_malformed_line() -> None:
    text = b"".join(f"{n}!00_{'A' * 22}\r\n".encode() for n in EXPORTS) + b"<html>\r\n"
    raw = lzma.compress(text, format=lzma.FORMAT_ALONE)
    with pytest.raises(IndexError_, match="malformed"):
        decode_index(raw)
