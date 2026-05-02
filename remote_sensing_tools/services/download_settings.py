"""Shared constants for imagery download task execution."""

from __future__ import annotations

import httpx


DOWNLOAD_CHUNK_SIZE = 1024 * 1024
DOWNLOAD_MAX_ATTEMPTS = 4
DOWNLOAD_RETRY_DELAYS = (2, 5, 10)
DOWNLOAD_MAX_RETRIES = len(DOWNLOAD_RETRY_DELAYS)

ALLOWED_DOWNLOAD_URL_HOSTS = {
    "planetarycomputer.microsoft.com",
    "landsatlook.usgs.gov",
    "ers.cr.usgs.gov",
}
ALLOWED_DOWNLOAD_URL_SUFFIXES = (
    ".blob.core.windows.net",
    ".usgs.gov",
)

RETRYABLE_DOWNLOAD_EXCEPTIONS = (
    httpx.RemoteProtocolError,
    httpx.ReadError,
    httpx.WriteError,
    httpx.ConnectError,
    httpx.TimeoutException,
)
