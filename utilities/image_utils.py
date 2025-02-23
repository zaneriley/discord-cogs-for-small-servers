import logging
from abc import ABC, abstractmethod

import aiofiles
import aiohttp
from discord import Asset

logger = logging.getLogger(__name__)


class BaseImageHandler(ABC):
    @abstractmethod
    async def fetch_image_data(self) -> bytes:
        """Fetches image data in bytes. Implementers should handle common exceptions."""


class LocalImageHandler(BaseImageHandler):
    def __init__(self, file_path: str):
        self.file_path = file_path

    async def fetch_image_data(self) -> bytes:
        try:
            async with aiofiles.open(self.file_path, "rb") as file:
                return await file.read()
        except FileNotFoundError:
            logger.exception("File not found: %s", self.file_path)
            raise
        except Exception:
            logger.exception("Error reading file %s:", self.file_path)
            raise


class URLImageHandler(BaseImageHandler):
    def __init__(self, url: str):
        self.url = url

    async def _fetch(self, session):
        async with session.get(self.url) as response:
            if response.status == 200:
                return await response.read()
            error_message = f"Failed to fetch image from URL: {self.url} with status {response.status}"
            raise Exception(error_message)

    async def fetch_image_data(self) -> bytes:
        try:
            async with aiohttp.ClientSession() as session:
                return await self._fetch(session)
        except Exception:
            logger.exception("Error fetching image from URL %s", self.url)
            raise


class DiscordImageHandler(BaseImageHandler):
    def __init__(self, asset: Asset):
        self.asset = asset

    async def fetch_image_data(self) -> bytes:
        try:
            return await self.asset.read()
        except Exception:
            logger.exception("Error fetching Discord asset:")
            raise


def get_image_handler(source) -> BaseImageHandler:
    if isinstance(source, Asset):
        return DiscordImageHandler(source)
    if isinstance(source, str) and source.startswith(("http://", "https://")):
        return URLImageHandler(source)
    if isinstance(source, str):
        return LocalImageHandler(source)
    error_message = "Invalid image source provided"
    raise ValueError(error_message)
