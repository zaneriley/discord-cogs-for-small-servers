from abc import ABC, abstractmethod
import aiofiles
import aiohttp
from discord import Asset
import logging

logger = logging.getLogger(__name__)

class BaseImageHandler(ABC):
    @abstractmethod
    async def fetch_image_data(self) -> bytes:
        """Fetches image data in bytes. Implementers should handle common exceptions."""
        pass

class LocalImageHandler(BaseImageHandler):
    def __init__(self, file_path: str):
        self.file_path = file_path

    async def fetch_image_data(self) -> bytes:
        try:
            async with aiofiles.open(self.file_path, 'rb') as file:
                return await file.read()
        except FileNotFoundError:
            logger.error(f"File not found: {self.file_path}")
            raise
        except Exception as e:
            logger.error(f"Error reading file {self.file_path}: {e}")
            raise

class URLImageHandler(BaseImageHandler):
    def __init__(self, url: str):
        self.url = url

    async def fetch_image_data(self) -> bytes:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        raise Exception(f"Failed to fetch image from URL: {self.url} with status {response.status}")
        except Exception as e:
            logger.error(f"Error fetching image from URL {self.url}: {e}")
            raise

class DiscordImageHandler(BaseImageHandler):
    def __init__(self, asset: Asset):
        self.asset = asset

    async def fetch_image_data(self) -> bytes:
        try:
            return await self.asset.read()
        except Exception as e:
            logger.error(f"Error fetching Discord asset: {e}")
            raise

def get_image_handler(source) -> BaseImageHandler:
    if isinstance(source, Asset):
        return DiscordImageHandler(source)
    elif isinstance(source, str) and (source.startswith('http://') or source.startswith('https://')):
        return URLImageHandler(source)
    elif isinstance(source, str):
        return LocalImageHandler(source)
    else:
        raise ValueError("Invalid image source provided")
