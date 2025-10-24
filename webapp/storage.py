"""Blob storage helpers."""

from __future__ import annotations

import logging
from typing import Optional

try:
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobClient, BlobServiceClient
except ImportError:  # pragma: no cover - allow running without Azure SDK during tests
    DefaultAzureCredential = None
    BlobClient = BlobServiceClient = None

logger = logging.getLogger(__name__)

_service_client: Optional[BlobServiceClient] = None


def get_blob_service(account_url: str) -> BlobServiceClient:
    global _service_client
    if _service_client is None:
        if DefaultAzureCredential is None or BlobServiceClient is None:
            raise RuntimeError("Azure SDK is not installed")
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        _service_client = BlobServiceClient(account_url=account_url, credential=credential)
        logger.info("Blob service client initialised")
    return _service_client


def get_blob_client(account_url: str, container: str, blob_name: str) -> BlobClient:
    service = get_blob_service(account_url)
    return service.get_blob_client(container=container, blob=blob_name)
