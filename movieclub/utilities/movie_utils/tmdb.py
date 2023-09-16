import os
import requests
import logging
from dotenv import load_dotenv
from typing import Union, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '../../../.env'))

API_BASE_URL = "https://api.themoviedb.org/3"
API_KEY = os.getenv("TMDB_API_KEY")

if not API_KEY:
    logging.error("TMDB_API_KEY not found in environment variables.")
    exit(1)

def fetch_movie_details(movie_name: str) -> Union[Dict[str, Any], None]:
    """
    Fetches movie details from TMDb API by movie name.
    
    Parameters:
    movie_name (str): Name of the movie to search for.

    Returns:
    dict: Details of the movie if found, None otherwise.
    """
    try:
        search_url = f"{API_BASE_URL}/search/movie"
        params = {
            "api_key": API_KEY,
            "query": movie_name
        }
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching movie details: {e}")
        return None
    
if __name__ == "__main__":
    movie_details = fetch_movie_details("Inception")
    logging.info(movie_details)
