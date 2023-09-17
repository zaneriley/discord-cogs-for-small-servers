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

        if not data['results']:
            logging.error(f"No results found for the movie name: {movie_name}")
            return None

        movie_data = data['results'][0]

        movie_details = {
            "title": {
                "label": "Title",
                "type": "short_text",
                "value": movie_data.get('title', 'N/A')
            },
            "genre": {
                "label": "Genre",
                "type": "short_text",
                "value": "Pre-fetched Genre"  # To be filled after fetching genre details
            },
            "year": {
                "label": "Year",
                "type": "number",
                "value": int(movie_data['release_date'].split('-')[0]) if movie_data.get('release_date') else 'N/A'
            },
            "poster_url": {
                "label": "Poster URL",
                "type": "short_text",
                "value": f"https://image.tmdb.org/t/p/w500{movie_data.get('poster_path', '')}" if movie_data.get('poster_path') else 'N/A'
            },
            "trailer_url": {
                "label": "Trailer URL",
                "type": "short_text",
                "value": "Pre-fetched Trailer URL"  # To be filled after fetching trailer details
            },
            "fan_count": {
                "label": "Fan Count",
                "type": "number",
                "value": "Pre-fetched Fan Count"  # To be filled after fetching fan count details
            }
        }
        return movie_details

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching movie details: {e}")
        return None

    
if __name__ == "__main__":
    movie_details = fetch_movie_details("Inception")
    logging.info(movie_details)
