import io
import shutil
from pathlib import Path
from typing import BinaryIO, Optional, Tuple

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import HTTPException
from fastapi.responses import FileResponse, Response
from PIL import Image, UnidentifiedImageError

from config import get_settings


settings = get_settings()


class FileStore:
    """Storage facade supporting local disk and S3-compatible object stores."""

    def __init__(self):
        self.backend = settings.storage_backend.lower().strip()
        self.base_path = Path(settings.storage_path)
        self.pdf_path = self.base_path / "pdfs"
        self.figures_path = self.base_path / "figures"
        self.graphs_path = self.base_path / "graphs"
        self.cache_path = Path(settings.storage_cache_path)

        self.pdf_cache_path = self.cache_path / "pdfs"
        self.image_cache_path = self.cache_path / "images"

        self._s3_client = None
        self._bucket = settings.storage_bucket.strip()
        self._prefix = settings.storage_prefix.strip("/")

        if self.backend == "s3":
            if not self._bucket:
                raise RuntimeError("STORAGE_BUCKET must be configured when STORAGE_BACKEND=s3")

            self._s3_client = boto3.client(
                "s3",
                endpoint_url=settings.storage_endpoint_url or None,
                aws_access_key_id=settings.storage_access_key_id or None,
                aws_secret_access_key=settings.storage_secret_access_key or None,
                region_name=settings.storage_region or None,
                config=Config(
                    s3={
                        "addressing_style": "path" if settings.storage_force_path_style else "auto"
                    }
                ),
            )

            self.pdf_cache_path.mkdir(parents=True, exist_ok=True)
            self.image_cache_path.mkdir(parents=True, exist_ok=True)
        else:
            self.pdf_path.mkdir(parents=True, exist_ok=True)
            self.figures_path.mkdir(parents=True, exist_ok=True)
            self.graphs_path.mkdir(parents=True, exist_ok=True)

    def _object_key(self, category: str, filename: str) -> str:
        if self._prefix:
            return f"{self._prefix}/{category}/{filename}"
        return f"{category}/{filename}"

    def _s3_ref(self, key: str, bucket: Optional[str] = None) -> str:
        target_bucket = bucket or self._bucket
        return f"s3://{target_bucket}/{key}"

    def _parse_s3_ref(self, ref: str) -> Tuple[str, str]:
        if ref.startswith("s3://"):
            without_scheme = ref[5:]
            parts = without_scheme.split("/", 1)
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise ValueError(f"Invalid S3 reference: {ref}")
            return parts[0], parts[1]
        return self._bucket, ref.lstrip("/")

    def save_pdf(self, document_id: str, file: BinaryIO, filename: str) -> str:
        """Save uploaded PDF and return storage reference."""
        if self.backend == "s3":
            key = self._object_key("pdfs", f"{document_id}.pdf")
            file.seek(0)
            self._s3_client.upload_fileobj(
                file,
                self._bucket,
                key,
                ExtraArgs={"ContentType": "application/pdf"},
            )
            return self._s3_ref(key)

        file_path = self.pdf_path / f"{document_id}.pdf"
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file, f)
        return str(file_path)

    def save_figure(self, document_id: str, page_num: int, fig_index: int, image_bytes: bytes) -> str:
        """Save extracted figure image and return storage reference."""
        filename = f"{document_id}_p{page_num}_fig{fig_index}.png"

        if self.backend == "s3":
            key = self._object_key("figures", filename)
            self._s3_client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=image_bytes,
                ContentType="image/png",
            )
            return self._s3_ref(key)

        file_path = self.figures_path / filename
        with open(file_path, "wb") as f:
            f.write(image_bytes)
        return str(file_path)

    def save_graph(self, document_id: str, graph_data: bytes) -> str:
        """Save serialized NetworkX graph and return storage reference."""
        if self.backend == "s3":
            key = self._object_key("graphs", f"{document_id}.pkl")
            self._s3_client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=graph_data,
                ContentType="application/octet-stream",
            )
            return self._s3_ref(key)

        file_path = self.graphs_path / f"{document_id}.pkl"
        with open(file_path, "wb") as f:
            f.write(graph_data)
        return str(file_path)

    def load_graph(self, document_id: str) -> bytes:
        """Load serialized graph bytes."""
        if self.backend == "s3":
            key = self._object_key("graphs", f"{document_id}.pkl")
            result = self._s3_client.get_object(Bucket=self._bucket, Key=key)
            return result["Body"].read()

        file_path = self.graphs_path / f"{document_id}.pkl"
        with open(file_path, "rb") as f:
            return f.read()

    def get_pdf_path(self, document_id: str) -> str:
        """Get storage reference to PDF file."""
        if self.backend == "s3":
            key = self._object_key("pdfs", f"{document_id}.pdf")
            return self._s3_ref(key)
        return str(self.pdf_path / f"{document_id}.pdf")

    def resolve_pdf_for_processing(self, file_ref: str, document_id: str) -> str:
        """Ensure PDF is available locally for PyMuPDF/Tesseract processing."""
        if self.backend != "s3":
            return file_ref

        bucket, key = self._parse_s3_ref(file_ref)
        local_path = self.pdf_cache_path / f"{document_id}.pdf"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        self._s3_client.download_file(bucket, key, str(local_path))
        return str(local_path)

    def ensure_local_image_for_llm(self, image_ref: str, cache_hint: str) -> Optional[str]:
        """Ensure a figure image exists locally for multimodal model clients."""
        if not image_ref:
            return None

        if self.backend != "s3":
            path = Path(image_ref)
            if path.exists() and path.is_file() and self.is_usable_image(image_ref):
                return str(path)
            return None

        bucket, key = self._parse_s3_ref(image_ref)
        suffix = Path(key).suffix or ".png"
        safe_hint = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in cache_hint)
        local_path = self.image_cache_path / f"{safe_hint}{suffix}"
        local_path.parent.mkdir(parents=True, exist_ok=True)

        if not local_path.exists():
            self._s3_client.download_file(bucket, key, str(local_path))

        if self.is_usable_image(str(local_path)):
            return str(local_path)
        return None

    def get_figure_response(self, image_ref: str):
        """Return FastAPI response for figure image regardless of storage backend."""
        if self.backend != "s3":
            path = Path(image_ref)
            if not path.exists() or not path.is_file():
                raise HTTPException(status_code=404, detail="Figure not found")
            return FileResponse(str(path))

        try:
            bucket, key = self._parse_s3_ref(image_ref)
            result = self._s3_client.get_object(Bucket=bucket, Key=key)
            content_type = result.get("ContentType") or "image/png"
            return Response(content=result["Body"].read(), media_type=content_type)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in {"NoSuchKey", "404", "NotFound"}:
                raise HTTPException(status_code=404, detail="Figure not found")
            raise HTTPException(status_code=500, detail="Failed to read figure image")

    def is_usable_image(self, image_ref: str) -> bool:
        """Validate image exists and is not mostly-black noise."""
        if not image_ref:
            return False

        if self.backend != "s3" or not image_ref.startswith("s3://"):
            path = Path(image_ref)
            if not path.exists() or not path.is_file():
                return False
            try:
                with Image.open(path) as img:
                    return self._is_usable_pil_image(img)
            except (OSError, UnidentifiedImageError, ValueError):
                return False

        try:
            bucket, key = self._parse_s3_ref(image_ref)
            obj = self._s3_client.get_object(Bucket=bucket, Key=key)
            image_bytes = obj["Body"].read()
            with Image.open(io.BytesIO(image_bytes)) as img:
                return self._is_usable_pil_image(img)
        except (ClientError, OSError, UnidentifiedImageError, ValueError):
            return False

    def _is_usable_pil_image(self, img: Image.Image) -> bool:
        gray = img.convert("L")
        extrema = gray.getextrema()
        if not extrema:
            return False

        _, max_px = extrema
        if max_px <= 8:
            return False

        histogram = gray.histogram()
        total = sum(histogram) or 1
        dark_ratio = sum(histogram[:8]) / total
        return dark_ratio <= 0.985

    def cleanup_processing_cache(self, document_id: str):
        """Cleanup temporary local cache artifacts for a document."""
        for path in [self.pdf_cache_path / f"{document_id}.pdf"]:
            if path.exists() and path.is_file():
                path.unlink()

    def get_figure_path(self, image_path: str) -> str:
        """Return stored figure reference (legacy helper)."""
        return image_path

    def delete_document_files(self, document_id: str):
        """Delete all files for a document from configured storage backend."""
        if self.backend == "s3":
            keys = [
                self._object_key("pdfs", f"{document_id}.pdf"),
                self._object_key("graphs", f"{document_id}.pkl"),
            ]

            figure_prefix = self._object_key("figures", f"{document_id}_")
            paginator = self._s3_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._bucket, Prefix=figure_prefix):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])

            unique_keys = list(dict.fromkeys(keys))
            for i in range(0, len(unique_keys), 1000):
                batch = unique_keys[i:i + 1000]
                self._s3_client.delete_objects(
                    Bucket=self._bucket,
                    Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
                )

            self.cleanup_processing_cache(document_id)
            return

        pdf_file = self.pdf_path / f"{document_id}.pdf"
        if pdf_file.exists():
            pdf_file.unlink()

        for fig_file in self.figures_path.glob(f"{document_id}_*"):
            fig_file.unlink()

        graph_file = self.graphs_path / f"{document_id}.pkl"
        if graph_file.exists():
            graph_file.unlink()