"""S3 temporary storage service for MinerU PDF hosting."""

import asyncio
import logging
import uuid

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.exceptions import PDFProcessingError

logger = logging.getLogger(__name__)


class S3TempStorage:
    """Handles temporary PDF storage in S3 for MinerU API access."""

    def __init__(self):
        """Initialize S3 client."""
        if not settings.AWS_S3_TEMP_BUCKET:
            raise ValueError("AWS_S3_TEMP_BUCKET not configured")

        self.bucket = settings.AWS_S3_TEMP_BUCKET
        self.prefix = "temp/"  # Hardcoded default
        self.presigned_expiration = 3600  # 1 hour, hardcoded default

        # Initialize S3 client (uses AWS credentials from environment or IAM role)
        self.s3_client = boto3.client("s3", region_name="us-east-1")
        logger.debug(f"🪣 S3TempStorage initialized - bucket: {self.bucket}")

    async def upload_pdf(self, pdf_content: bytes) -> str:
        """Upload PDF to S3 and return the S3 key.

        Args:
            pdf_content: PDF file content as bytes

        Returns:
            S3 object key

        Raises:
            PDFProcessingError: If upload fails
        """
        # Generate unique key
        file_id = str(uuid.uuid4())
        s3_key = f"{self.prefix}{file_id}.pdf"

        def _upload():
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=pdf_content,
                ContentType="application/pdf",
            )

        try:
            logger.info(f"📤 Uploading PDF to S3: {s3_key}")

            # Run synchronous boto3 call in thread pool to avoid blocking event loop
            await asyncio.to_thread(_upload)

            logger.info(f"✅ PDF uploaded successfully: {s3_key}")
            return s3_key

        except ClientError as e:
            error_msg = f"Failed to upload PDF to S3: {e}"
            logger.error(f"❌ {error_msg}")
            raise PDFProcessingError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error uploading to S3: {e}"
            logger.error(f"❌ {error_msg}")
            raise PDFProcessingError(error_msg)

    def generate_presigned_url(self, s3_key: str) -> str:
        """Generate presigned URL for S3 object.

        Args:
            s3_key: S3 object key

        Returns:
            Presigned URL (valid for 1 hour)

        Raises:
            PDFProcessingError: If URL generation fails
        """
        try:
            logger.debug(f"🔗 Generating presigned URL for: {s3_key}")

            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": s3_key},
                ExpiresIn=self.presigned_expiration,
            )

            logger.debug(f"✅ Presigned URL generated (expires in {self.presigned_expiration}s)")
            return url

        except ClientError as e:
            error_msg = f"Failed to generate presigned URL: {e}"
            logger.error(f"❌ {error_msg}")
            raise PDFProcessingError(error_msg)

    async def delete_pdf(self, s3_key: str) -> None:
        """Delete PDF from S3.

        Args:
            s3_key: S3 object key

        Note:
            Failures are logged but not raised (cleanup is best-effort)
        """

        def _delete():
            self.s3_client.delete_object(Bucket=self.bucket, Key=s3_key)

        try:
            logger.info(f"🗑️ Deleting temp file from S3: {s3_key}")

            # Run synchronous boto3 call in thread pool to avoid blocking event loop
            await asyncio.to_thread(_delete)

            logger.info(f"✅ Temp file deleted successfully: {s3_key}")

        except ClientError as e:
            logger.warning(f"⚠️ Failed to delete S3 temp file {s3_key}: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Unexpected error deleting S3 temp file {s3_key}: {e}")

    async def upload_and_get_url(self, pdf_content: bytes) -> tuple[str, str]:
        """Upload PDF and generate presigned URL in one call.

        Args:
            pdf_content: PDF file content as bytes

        Returns:
            Tuple of (s3_key, presigned_url)

        Raises:
            PDFProcessingError: If upload or URL generation fails
        """
        s3_key = await self.upload_pdf(pdf_content)
        presigned_url = self.generate_presigned_url(s3_key)
        return s3_key, presigned_url
