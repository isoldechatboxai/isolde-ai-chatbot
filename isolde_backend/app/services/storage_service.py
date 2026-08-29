import os
from pathlib import Path

from flask import current_app


class StorageNotConfigured(RuntimeError):
    pass


class StorageService:
    """Private local or S3-compatible object storage."""

    def __init__(self, config):
        self.backend = config.get("STORAGE_BACKEND", "local").lower()
        self.root = Path(config["UPLOAD_FOLDER"]).resolve()
        self.bucket = config.get("S3_BUCKET", "")
        self.region = config.get("S3_REGION") or None
        self.endpoint = config.get("S3_ENDPOINT_URL") or None
        self.access_key = config.get("S3_ACCESS_KEY_ID") or None
        self.secret_key = config.get("S3_SECRET_ACCESS_KEY") or None
        if self.backend not in {"local", "s3"}:
            raise StorageNotConfigured("Unsupported storage backend.")
        if self.backend == "s3" and not self.bucket:
            raise StorageNotConfigured("S3_BUCKET is required for S3 storage.")

    def _local_path(self, key):
        candidate = (self.root / key).resolve()
        if self.root != candidate and self.root not in candidate.parents:
            raise ValueError("Invalid storage key.")
        return candidate

    def _s3(self):
        try:
            import boto3
        except ImportError as exc:
            raise StorageNotConfigured("S3 storage dependency is unavailable.") from exc
        return boto3.client(
            "s3", region_name=self.region, endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key, aws_secret_access_key=self.secret_key,
        )

    def put_file(self, key, source_path, content_type):
        if self.backend == "local":
            target = self._local_path(key)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source_path, target)
            return
        self._s3().upload_file(
            source_path, self.bucket, key,
            ExtraArgs={"ContentType": content_type, "ServerSideEncryption": "AES256"},
        )

    def read_bytes(self, key):
        if self.backend == "local":
            return self._local_path(key).read_bytes()
        return self._s3().get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key):
        if self.backend == "local":
            path = self._local_path(key)
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            return
        self._s3().delete_object(Bucket=self.bucket, Key=key)

    def check(self):
        if self.backend == "local":
            self.root.mkdir(parents=True, exist_ok=True)
            return self.root.is_dir()
        self._s3().head_bucket(Bucket=self.bucket)
        return True


def get_storage():
    return StorageService(current_app.config)
