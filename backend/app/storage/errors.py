from __future__ import annotations


class StorageError(RuntimeError):
    """Base class for storage-layer failures."""


class StorageConfigurationError(StorageError):
    """Raised when a selected storage backend is not configured safely."""


class InvalidStorageKeyError(StorageError, ValueError):
    """Raised when a storage key would escape the configured namespace."""


class StorageObjectNotFoundError(StorageError, FileNotFoundError):
    """Raised when a requested storage object does not exist."""
