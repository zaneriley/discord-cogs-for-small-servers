from tmdb import TMDbHandler
from movie_data_fetcher import MovieDetailsFetcher

def main():
    # Instantiate the API handler
    tmdb_handler = TMDbHandler()
    
    # Instantiate the movie details fetcher with the API handler
    movie_details_fetcher = MovieDetailsFetcher(api_handler=tmdb_handler)
    
    # Fetch and print movie details to test the integration
    movie_details = movie_details_fetcher.get_movie_details("Inception")
    print(movie_details)

if __name__ == "__main__":
    main()
