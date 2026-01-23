"""AWS S3 service for screenshot storage"""
import asyncio
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from datetime import datetime, timedelta
from typing import Optional
import structlog
from config.settings import settings

logger = structlog.get_logger()


class S3Service:
    """Handle screenshot uploads to AWS S3"""

    def __init__(self):
        """Initialize S3 client"""
        self.bucket_name = settings.aws_s3_bucket
        self.region = settings.aws_s3_region

        # Initialize boto3 client
        session_kwargs = {"region_name": self.region}
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            session_kwargs.update({
                "aws_access_key_id": settings.aws_access_key_id,
                "aws_secret_access_key": settings.aws_secret_access_key,
            })

        self.s3_client = boto3.client('s3', **session_kwargs)

        logger.info("s3_service_initialized",
                   bucket=self.bucket_name,
                   region=self.region)

    def _generate_s3_key(self, domain: str, timestamp: datetime) -> str:
        """
        Generate S3 key with date-based hierarchy

        Format: screenshots/YYYY/MM/DD/domain-ai_timestamp.png
        Example: screenshots/2025/11/22/autoai-ai_1732276800.png
        """
        # Replace dots with dashes for cleaner keys
        clean_domain = domain.replace('.', '-')

        # Date-based folder structure
        date_path = timestamp.strftime("%Y/%m/%d")

        # Unix timestamp for uniqueness
        unix_ts = int(timestamp.timestamp())

        return f"screenshots/{date_path}/{clean_domain}_{unix_ts}.png"

    async def upload_screenshot(
        self,
        screenshot_bytes: bytes,
        domain: str,
        timestamp: Optional[datetime] = None
    ) -> tuple[str, str]:
        """
        Upload screenshot to S3

        Args:
            screenshot_bytes: PNG image bytes
            domain: Domain name (e.g., "autoai.ai")
            timestamp: Optional timestamp (defaults to now)

        Returns:
            Tuple of (s3_url, s3_key)

        Raises:
            Exception on upload failure
        """
        if not timestamp:
            timestamp = datetime.utcnow()

        s3_key = self._generate_s3_key(domain, timestamp)

        try:
            # Run boto3 upload in thread pool (it's not async)
            await asyncio.to_thread(
                self.s3_client.put_object,
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=screenshot_bytes,
                ContentType='image/png',
                Metadata={
                    'domain': domain,
                    'captured_at': timestamp.isoformat(),
                }
            )

            # Generate public URL
            s3_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"

            logger.info("screenshot_uploaded_to_s3",
                       domain=domain,
                       s3_key=s3_key,
                       size_kb=len(screenshot_bytes) / 1024)

            return s3_url, s3_key

        except (ClientError, BotoCoreError) as e:
            logger.error("s3_upload_failed",
                        domain=domain,
                        error=str(e))
            raise

    async def generate_presigned_url(
        self,
        s3_key: str,
        expiration: int = 3600
    ) -> str:
        """
        Generate a presigned URL for private S3 objects

        Args:
            s3_key: S3 object key
            expiration: URL expiration time in seconds (default 1 hour)

        Returns:
            Presigned URL string
        """
        try:
            url = await asyncio.to_thread(
                self.s3_client.generate_presigned_url,
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return url
        except (ClientError, BotoCoreError) as e:
            logger.error("presigned_url_failed", s3_key=s3_key, error=str(e))
            raise

    async def delete_screenshot(self, s3_key: str) -> bool:
        """
        Delete screenshot from S3

        Args:
            s3_key: S3 object key to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            await asyncio.to_thread(
                self.s3_client.delete_object,
                Bucket=self.bucket_name,
                Key=s3_key
            )
            logger.info("screenshot_deleted_from_s3", s3_key=s3_key)
            return True
        except (ClientError, BotoCoreError) as e:
            logger.error("s3_delete_failed", s3_key=s3_key, error=str(e))
            return False

    async def check_bucket_exists(self) -> bool:
        """
        Verify S3 bucket exists and is accessible

        Returns:
            True if bucket exists and accessible
        """
        try:
            await asyncio.to_thread(
                self.s3_client.head_bucket,
                Bucket=self.bucket_name
            )
            logger.info("s3_bucket_verified", bucket=self.bucket_name)
            return True
        except (ClientError, BotoCoreError) as e:
            logger.error("s3_bucket_check_failed",
                        bucket=self.bucket_name,
                        error=str(e))
            return False
