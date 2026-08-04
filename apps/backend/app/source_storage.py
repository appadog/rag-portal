"""Immutable source-file storage adapters for reproducible parsing runs."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import quote

import httpx


class SourceStorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredSource:
    key: str
    backend: str
    created: bool


class SourceStorage:
    backend: str

    def put_if_absent(self, key: str, data: bytes) -> StoredSource:
        raise NotImplementedError

    def get(self, key: str) -> bytes:
        raise NotImplementedError


class LocalFilesystemSourceStorage(SourceStorage):
    backend = "local_filesystem"

    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def path_for(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        root = self.root.resolve()
        if root != candidate and root not in candidate.parents:
            raise SourceStorageError("invalid source storage key")
        return candidate

    def put_if_absent(self, key: str, data: bytes) -> StoredSource:
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            return StoredSource(key=key, backend=self.backend, created=False)
        temporary = path.with_name(path.name + ".pending")
        try:
            with temporary.open("xb") as handle:
                handle.write(data)
            os.replace(temporary, path)
        except FileExistsError:
            return StoredSource(key=key, backend=self.backend, created=False)
        finally:
            if temporary.exists():
                temporary.unlink(missing_ok=True)
        return StoredSource(key=key, backend=self.backend, created=True)

    def get(self, key: str) -> bytes:
        try:
            return self.path_for(key).read_bytes()
        except FileNotFoundError as error:
            raise SourceStorageError(f"stored source is missing: {key}") from error


class HttpObjectSourceStorage(SourceStorage):
    """Path-style object-store adapter for an authenticated internal gateway.

    The gateway contract is deliberately small: PUT/GET
    `{RAG_OBJECT_STORAGE_ENDPOINT}/{bucket}/{key}`. Deployments that use S3,
    MinIO, or another store can put signing/auth behind that gateway without
    changing application provenance records.
    """

    backend = "http_object_storage"

    def __init__(self, endpoint: str, bucket: str, token: str | None = None) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.bucket = bucket.strip("/")
        self.token = token
        if not self.endpoint or not self.bucket:
            raise SourceStorageError("object storage needs RAG_OBJECT_STORAGE_ENDPOINT and RAG_OBJECT_STORAGE_BUCKET")

    def url_for(self, key: str) -> str:
        return f"{self.endpoint}/{quote(self.bucket, safe='')}/{quote(key, safe='/')}"

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def put_if_absent(self, key: str, data: bytes) -> StoredSource:
        try:
            response = httpx.put(
                self.url_for(key),
                content=data,
                headers={**self.headers(), "If-None-Match": "*"},
                timeout=float(os.getenv("RAG_OBJECT_STORAGE_TIMEOUT_SECONDS", "30")),
            )
        except Exception as error:
            raise SourceStorageError(f"object storage upload failed: {error}") from error
        if response.status_code in {200, 201, 204}:
            return StoredSource(key=key, backend=self.backend, created=True)
        if response.status_code in {409, 412}:
            return StoredSource(key=key, backend=self.backend, created=False)
        raise SourceStorageError(f"object storage upload failed with HTTP {response.status_code}")

    def get(self, key: str) -> bytes:
        try:
            response = httpx.get(
                self.url_for(key),
                headers=self.headers(),
                timeout=float(os.getenv("RAG_OBJECT_STORAGE_TIMEOUT_SECONDS", "30")),
            )
            response.raise_for_status()
            return response.content
        except Exception as error:
            raise SourceStorageError(f"object storage download failed: {error}") from error


def source_storage() -> SourceStorage:
    backend = os.getenv("RAG_SOURCE_STORAGE_BACKEND", "local").lower()
    if backend in {"local", "filesystem", "local_filesystem"}:
        return LocalFilesystemSourceStorage(os.getenv("RAG_SOURCE_STORAGE_PATH", ".rag-sources"))
    if backend in {"object", "http_object", "http_object_storage"}:
        return HttpObjectSourceStorage(
            os.getenv("RAG_OBJECT_STORAGE_ENDPOINT", ""),
            os.getenv("RAG_OBJECT_STORAGE_BUCKET", ""),
            os.getenv("RAG_OBJECT_STORAGE_TOKEN"),
        )
    raise SourceStorageError(f"unsupported RAG_SOURCE_STORAGE_BACKEND: {backend}")
