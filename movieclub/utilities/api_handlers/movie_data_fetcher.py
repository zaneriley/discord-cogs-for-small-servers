# from ..data_management.movie_dictionary import MovieDictionary
from api_handler import BaseAPIHandler

class MovieDetailsFetcher:
    def __init__(self, api_handler: BaseAPIHandler):
        self.api_handler = api_handler

    def get_movie_details(self, movie_name: str):
        return self.api_handler.fetch_movie_details(movie_name)
