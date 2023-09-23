import os
import requests
import logging
from dotenv import load_dotenv
from typing import Union, Dict, Any, List

def configure_logging():
    """
    Configures logging settings.
    """
    logging.basicConfig(level=logging.INFO)

def load_environment_variables():
    """
    Load environment variables from the .env file.
    """
    load_dotenv(os.path.join(os.path.dirname(__file__), '../../../.env'))

def make_request(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Makes a GET request to the specified URL with the given parameters and returns the JSON response.
    """
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error making request to {url}: {e}")
        return None

def extract_movie_details(movie_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts movie details from the API response data.
    """
    genres = [genre['name'] for genre in movie_data.get('genres', [])]
    return {
        "title": movie_data.get('title', 'N/A'),
        "year_of_release": int(movie_data['release_date'].split('-')[0]) if movie_data.get('release_date') else 'N/A',
        "tagline": movie_data.get('tagline', 'N/A'),
        "genres": genres,
        "runtime": movie_data.get('runtime', 'N/A'),
        "poster_url": f"https://image.tmdb.org/t/p/w500{movie_data.get('poster_path', '')}" if movie_data.get('poster_path') else 'N/A',
        "trailer_link": f"https://www.youtube.com/watch?v={movie_data['videos']['results'][0]['key']}" if movie_data['videos']['results'] else 'N/A',
    }

def fetch_movie_details(movie_name: str) -> Union[Dict[str, Any], None]:
    """
    Fetches movie details from TMDb API by movie name.
    """
    API_BASE_URL = "https://api.themoviedb.org/3"
    API_KEY = os.getenv("TMDB_API_KEY")

    if not API_KEY:
        logging.error("TMDB_API_KEY not found in environment variables.")
        exit(1)

    # Step 1: Search for the movie to get its ID
    search_url = f"{API_BASE_URL}/search/movie"
    params = {
        "api_key": API_KEY,
        "query": movie_name
    }
    data = make_request(search_url, params)
    if not data or not data['results']:
        logging.error(f"No results found for the movie name: {movie_name}")
        return None

    movie_id = data['results'][0]['id']

    # Step 2: Use the movie ID to fetch detailed info
    movie_url = f"{API_BASE_URL}/movie/{movie_id}"
    params["append_to_response"] = "videos"  # Include videos (for trailer link) in the response
    movie_data = make_request(movie_url, params)
    if not movie_data:
        return None

    # Step 3: Extract the details
    return extract_movie_details(movie_data)

def main():
    """
    The main function to execute the script.
    """
    configure_logging()
    load_environment_variables()
    movie_details = fetch_movie_details("Inception")
    logging.info(movie_details)

if __name__ == "__main__":
    main()