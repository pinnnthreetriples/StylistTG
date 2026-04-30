# Storage architecture

StylistTG now separates application asset storage from TDLib runtime/session
storage.

## Storage categories

Application assets:

- profile photos;
- profile audio/music source and normalized files;
- story image/video source and normalized files.

These are addressed through storage keys such as:

```text
assets/<asset_id>/source/original.jpg
assets/<asset_id>/normalized/profile_photo.jpg
```

Storage keys use POSIX-style `/` separators internally. The local filesystem
adapter is the only layer that converts those keys to OS paths.

TDLib runtime/session storage:

- TDLib database directories;
- TDLib files directories;
- auth/session internals.

TDLib storage remains backend-only and is never exposed through public or signed
asset URLs.

## Backends

Local development uses:

```text
STORAGE_BACKEND=local
STORAGE_LOCAL_ROOT=backend/storage
TDLIB_STORAGE_BACKEND=local
TDLIB_DATABASE_ROOT=backend/tdlib/database
TDLIB_FILES_ROOT=backend/tdlib/files
```

The S3/R2/MinIO-compatible backend is implemented for application assets:

```text
STORAGE_BACKEND=s3
STORAGE_S3_ENDPOINT_URL=...
STORAGE_S3_BUCKET=...
STORAGE_S3_REGION=...
STORAGE_S3_ACCESS_KEY_ID=...
STORAGE_S3_SECRET_ACCESS_KEY=...
STORAGE_S3_FORCE_PATH_STYLE=true
STORAGE_S3_SIGNED_URL_EXPIRES_SECONDS=300
STORAGE_S3_PUBLIC_BASE_URL=
```

Configuration validation fails fast if `STORAGE_BACKEND=s3` is selected without
the required object-storage settings. The endpoint URL is configurable for R2
and MinIO. Secrets are never returned through API DTOs or logs.

The S3 adapter supports object save/read/exists/delete/stat/copy and signed URLs
for non-sensitive application assets. Signed URLs use the configured TTL and are
never generated for TDLib/session keys.

Cloud dev/staging validation is handled by:

```text
python -m app.scripts.cloud_config_check
python -m app.scripts.object_storage_smoke
```

The object storage smoke is dry-run by default. A real write/read/sign/delete
roundtrip requires `--allow-write-cloud` and only uses a `smoke/stylisttg/<uuid>/`
prefix.

## Compatibility

The `asset.source_path` and `asset.normalized_path` database fields remain
unchanged. Going forward they are treated as storage keys instead of OS-specific
paths. Existing local asset rows remain compatible as long as their paths are
relative to the configured local storage root.

Asset rows also store explicit storage metadata:

```text
storage_backend
storage_bucket
source_key
normalized_key
source_size_bytes
normalized_size_bytes
source_content_type
normalized_content_type
source_checksum
normalized_checksum
storage_migrated_at
```

Migration `20260430_0020` backfills existing local assets as
`storage_backend=local` and derives source/normalized keys from the legacy path
fields without deleting or changing the legacy values.

## Cleanup

The asset cleanup foundation is service-only and is not scheduled at startup.
It supports dry-run mode, a max delete count guard, and deletes only local
application asset directories under `assets/`. TDLib session directories are out
of scope and must not be cleaned by asset cleanup.
