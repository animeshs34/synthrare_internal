import os
import time
from pathlib import Path
from typing import IO

import boto3
from botocore.exceptions import ClientError

from app.config import settings

_MAX_RETRIES = 3


def _s3_client():
    return boto3.client(
        "s3",
        region_name=settings.do_spaces_region,
        endpoint_url=settings.do_spaces_endpoint,
        aws_access_key_id=settings.do_spaces_key,
        aws_secret_access_key=settings.do_spaces_secret,
    )


def _local_path(storage_path: str) -> Path:
    base = Path(settings.local_storage_path)
    base.mkdir(parents=True, exist_ok=True)
    return base / storage_path.lstrip("/")


def upload_file(file_obj: IO[bytes], storage_path: str, content_type: str = "application/octet-stream") -> str:
    """Upload a file and return its storage path."""
    if settings.use_local_storage:
        dest = _local_path(storage_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(file_obj.read())
        return storage_path

    client = _s3_client()
    for attempt in range(_MAX_RETRIES):
        try:
            client.upload_fileobj(
                file_obj,
                settings.do_spaces_bucket,
                storage_path,
                ExtraArgs={"ContentType": content_type},
            )
            return storage_path
        except ClientError as exc:
            if attempt == _MAX_RETRIES - 1:
                raise RuntimeError(f"Failed to upload after {_MAX_RETRIES} attempts") from exc
            time.sleep(2 ** attempt)

    return storage_path  # unreachable


def generate_download_url(storage_path: str, expires_in: int = 3600) -> str:
    """Return a presigned download URL (or absolute local file URL in dev)."""
    if settings.use_local_storage:
        return f"{settings.next_public_api_url}/files/{storage_path.lstrip('/')}"

    client = _s3_client()
    for attempt in range(_MAX_RETRIES):
        try:
            url: str = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.do_spaces_bucket, "Key": storage_path},
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as exc:
            if attempt == _MAX_RETRIES - 1:
                raise RuntimeError(f"Failed to generate URL after {_MAX_RETRIES} attempts") from exc
            time.sleep(2 ** attempt)

    return ""  # unreachable


def read_local_file(storage_path: str) -> bytes:
    """Read a local file (dev-only)."""
    dest = _local_path(storage_path)
    with open(dest, "rb") as f:
        return f.read()
