# api_handlers/__init__.py

from .api_handler import BaseAPIHandler  
from .tmdb import TMDbHandler 
from .movie_data_fetcher import MovieDetailsFetcher 
from .letterboxd import LetterboxdHandler

__all__ = [
    "BaseAPIHandler",
    "TMDbHandler",
    "MovieDetailsFetcher",
    "LetterboxdHandler"
]
