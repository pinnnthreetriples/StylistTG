from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.storage.base import StorageObject
from app.storage.errors import StorageObjectNotFoundError
from app.storage.paths import normalize_storage_key


class S3CompatibleStorageService:
    backend_name = "s3"

    def __init__(
        self,
        *,
        endpoint_url: str,
        bucket: str,
        region: str | None,
        access_key_id: str,
        secret_access_key: str,
        force_path_style: bool,
        public_base_url: str | None = None,
        client=None,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.bucket = bucket
        self.region = region or "us-east-1"
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.force_path_style = force_path_style
        self.public_base_url = public_base_url.rstrip("/") if public_base_url else None
        self.client = client or boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=self.region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(s3={"addressing_style": "path" if force_path_style else "virtual"}),
        )

    def save_bytes(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str | None = None,
        visibility: str = "private",
    ) -> StorageObject:
        normalized_key = normalize_storage_key(key)
        checksum = hashlib.sha256(content).hexdigest()
        kwargs = {
            "Bucket": self.bucket,
            "Key": normalized_key,
            "Body": content,
            "Metadata": {"sha256": checksum},
        }
        if content_type:
            kwargs["ContentType"] = content_type
        self.client.put_object(**kwargs)
        return StorageObject(
            key=normalized_key,
            path=None,
            uri=self.get_uri(normalized_key),
            size_bytes=len(content),
            content_type=content_type,
            checksum=checksum,
            storage_backend=self.backend_name,
            visibility=visibility,
            created_at=datetime.now(UTC),
        )

    def save_file(
        self,
        key: str,
        source_path: Path,
        *,
        content_type: str | None = None,
        visibility: str = "private",
    ) -> StorageObject:
        return self.save_bytes(
            key,
            source_path.read_bytes(),
            content_type=content_type,
            visibility=visibility,
        )

    def open_read(self, key: str) -> BinaryIO:
        return BytesIO(self.read_bytes(key))

    def read_bytes(self, key: str) -> bytes:
        normalized_key = normalize_storage_key(key)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=normalized_key)
        except ClientError as exc:
            if _client_error_code(exc) in {"NoSuchKey", "404", "NotFound"}:
                raise StorageObjectNotFoundError(normalized_key) from exc
            raise
        body = response["Body"]
        try:
            return body.read()
        finally:
            close = getattr(body, "close", None)
            if callable(close):
                close()

    def exists(self, key: str) -> bool:
        try:
            self.stat(key)
            return True
        except StorageObjectNotFoundError:
            return False

    def delete(self, key: str) -> bool:
        normalized_key = normalize_storage_key(key)
        existed = self.exists(normalized_key)
        self.client.delete_object(Bucket=self.bucket, Key=normalized_key)
        return existed

    def get_uri(self, key: str) -> str:
        normalized_key = normalize_storage_key(key)
        if self.public_base_url:
            return f"{self.public_base_url}/{normalized_key}"
        return f"s3://{self.bucket}/{normalized_key}"

    def get_signed_url(self, key: str, *, expires_seconds: int = 300) -> str:
        normalized_key = normalize_storage_key(key)
        if normalized_key.startswith("tdlib/"):
            raise ValueError("signed URLs are not allowed for TDLib session storage")
        self.stat(normalized_key)
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": normalized_key},
            ExpiresIn=expires_seconds,
        )

    def copy(self, source_key: str, destination_key: str) -> StorageObject:
        normalized_source = normalize_storage_key(source_key)
        normalized_destination = normalize_storage_key(destination_key)
        self.client.copy_object(
            Bucket=self.bucket,
            Key=normalized_destination,
            CopySource={"Bucket": self.bucket, "Key": normalized_source},
        )
        return self.stat(normalized_destination)

    def stat(self, key: str) -> StorageObject:
        normalized_key = normalize_storage_key(key)
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=normalized_key)
        except ClientError as exc:
            if _client_error_code(exc) in {"NoSuchKey", "404", "NotFound"}:
                raise StorageObjectNotFoundError(normalized_key) from exc
            raise
        metadata = response.get("Metadata") or {}
        return StorageObject(
            key=normalized_key,
            path=None,
            uri=self.get_uri(normalized_key),
            size_bytes=int(response.get("ContentLength") or 0),
            content_type=response.get("ContentType"),
            checksum=metadata.get("sha256") or _etag_checksum(response.get("ETag")),
            storage_backend=self.backend_name,
            visibility="private",
            created_at=response.get("LastModified"),
        )

    def cleanup_prefix(
        self,
        prefix: str,
        *,
        dry_run: bool = True,
        max_delete_count: int = 100,
    ) -> list[str]:
        normalized_prefix = normalize_storage_key(prefix).rstrip("/") + "/"
        deleted: list[str] = []
        continuation_token = None
        while True:
            kwargs = {"Bucket": self.bucket, "Prefix": normalized_prefix}
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token
            response = self.client.list_objects_v2(**kwargs)
            for item in response.get("Contents") or []:
                key = item["Key"]
                if len(deleted) >= max_delete_count:
                    raise ValueError("cleanup max delete count exceeded")
                if not dry_run:
                    self.client.delete_object(Bucket=self.bucket, Key=key)
                deleted.append(key)
            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")
        return deleted


def _client_error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code") or "")


def _etag_checksum(etag: str | None) -> str | None:
    if not etag:
        return None
    clean = etag.strip('"')
    if "-" in clean:
        return None
    return clean
