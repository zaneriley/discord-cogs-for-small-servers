import logging
import threading

# Set up logging configuration (this would ideally be in your main script or a separate config file)
logging.basicConfig(level=logging.INFO)

class MovieDictionary:
    _instance = None
    _lock = threading.Lock()  # Class level lock for thread-safety
    
    def __new__(cls):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(MovieDictionary, cls).__new__(cls)
                cls._instance.movie_data = {}  # Initialize empty movie_data dictionary
            return cls._instance

    def get_movie_details(self, movie_name: str) -> dict:
        """
        Get movie details by movie name.

        Args:
        - movie_name (str): Name of the movie.

        Returns:
        - dict: Movie details or an empty dictionary if not found.
        """
        return self.movie_data.get(movie_name, {})

    def update_movie_details(self, movie_name: str, details: dict) -> None:
        """
        Update movie details. This will verify and validate data before updating.

        Args:
        - movie_name (str): Name of the movie.
        - details (dict): Dictionary containing movie details.

        Returns:
        - None
        """
        with self._lock:
            try:
                if movie_name and isinstance(movie_name, str) and details and isinstance(details, dict):
                    # Additional validation can be added here to check the structure and values within the details dictionary
                    self.movie_data[movie_name] = details
                else:
                    logging.warning(f"Invalid data provided for movie: {movie_name}")
            except Exception as e:
                logging.error(f"Error updating movie details for {movie_name}: {e}")
