"""Tests for the downloader module (URL → filename + Content-Disposition parse)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from hub.downloader import (
    _filename_from_content_disposition,
    download_and_stage,
    filename_from_url,
)


class TestFilenameFromUrl:
    def test_normal(self) -> None:
        assert filename_from_url("https://e.com/files/foo.zip") == "foo.zip"

    def test_with_query_string(self) -> None:
        assert filename_from_url("https://e.com/files/foo.zip?download=1") == "foo.zip"

    def test_numeric_id_path(self) -> None:
        # figshare-style — falls through, returns the numeric id
        assert filename_from_url("https://ndownloader.figshare.com/files/8664388") == "8664388"

    def test_empty_path_raises(self) -> None:
        with pytest.raises(ValueError):
            filename_from_url("https://e.com/")


class TestFilenameFromContentDisposition:
    def test_empty(self) -> None:
        assert _filename_from_content_disposition("") is None

    def test_no_filename_param(self) -> None:
        assert _filename_from_content_disposition("inline") is None

    def test_simple_quoted(self) -> None:
        assert _filename_from_content_disposition(
            'attachment; filename="foo.zip"'
        ) == "foo.zip"

    def test_simple_unquoted(self) -> None:
        assert _filename_from_content_disposition(
            "attachment; filename=foo.zip"
        ) == "foo.zip"

    def test_rfc5987_percent_encoded(self) -> None:
        assert _filename_from_content_disposition(
            "attachment; filename*=UTF-8''foo%20bar.zip"
        ) == "foo bar.zip"

    def test_rfc5987_non_ascii(self) -> None:
        # Chinese filename: 中文.zip encoded as %E4%B8%AD%E6%96%87.zip
        assert _filename_from_content_disposition(
            "attachment; filename*=UTF-8''%E4%B8%AD%E6%96%87.zip"
        ) == "中文.zip"

    def test_prefers_filename_star_over_filename(self) -> None:
        """RFC 6266 §4.3 — filename* wins when both are present."""
        header = (
            "attachment; filename=\"ascii.zip\"; filename*=UTF-8''unicode%20foo.zip"
        )
        assert _filename_from_content_disposition(header) == "unicode foo.zip"


class FakeResponse:
    """Minimal stub matching requests.Response streaming interface."""

    def __init__(self, body: bytes, headers: dict[str, str] | None = None) -> None:
        self._body = body
        self.headers: dict[str, str] = headers or {"content-length": str(len(body))}

    def iter_content(self, chunk_size: int = 8192):
        i = 0
        while i < len(self._body):
            yield self._body[i:i + chunk_size]
            i += chunk_size

    def raise_for_status(self) -> None:
        pass

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *a: object) -> None:
        pass


def test_download_prefers_content_disposition_filename(tmp_path: Path) -> None:
    """Figshare-style numeric-ID URL + Content-Disposition header ⇒ real name wins."""
    body = b"col1,col2\n1,2\n"
    raw = tmp_path / "raw"
    raw.mkdir()

    response = FakeResponse(
        body,
        headers={
            "content-length": str(len(body)),
            "content-disposition": 'attachment; filename="cml_xsd.zip"',
        },
    )
    with patch("hub.downloader.requests.get", return_value=response):
        name, sha, size = download_and_stage(
            "https://ndownloader.figshare.com/files/8664388", raw
        )

    assert name == "cml_xsd.zip"
    assert (raw / "cml_xsd.zip").exists()
    assert (raw / "cml_xsd.zip").read_bytes() == body
    assert sha == hashlib.sha256(body).hexdigest()
    assert size == len(body)
    assert not (raw / ".partial").exists()


def test_download_falls_back_to_url_when_no_content_disposition(tmp_path: Path) -> None:
    """No CD header ⇒ filename comes from URL path as before."""
    body = b"hello"
    raw = tmp_path / "raw"
    raw.mkdir()

    response = FakeResponse(body)  # no content-disposition in headers
    with patch("hub.downloader.requests.get", return_value=response):
        name, _, _ = download_and_stage("https://example.com/files/hello.txt", raw)

    assert name == "hello.txt"
    assert (raw / "hello.txt").exists()


def test_download_ignores_content_disposition_without_filename_param(tmp_path: Path) -> None:
    """CD header but no filename parameter ⇒ fall back to URL."""
    body = b"hello"
    raw = tmp_path / "raw"
    raw.mkdir()

    response = FakeResponse(body, headers={
        "content-length": str(len(body)),
        "content-disposition": "inline",
    })
    with patch("hub.downloader.requests.get", return_value=response):
        name, _, _ = download_and_stage("https://example.com/files/hello.txt", raw)

    assert name == "hello.txt"
