import requests
from bs4 import BeautifulSoup
import json
import logging
from typing import List, Dict, Union, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def construct_url(film: str, year: Optional[str] = None) -> str:
    """Constructs the URL based on the film name and optionally the year."""
    base_url = f"https://letterboxd.com/film/{film}"
    if year:
        return f"{base_url}-{year}/reviews/by/activity/"
    else:
        return f"{base_url}/reviews/by/activity/"

def fetch_reviews(url: str) -> Optional[str]:
    """Fetches the reviews from the constructed URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch reviews: {e}")
        return None

def parse_review_data(page_content: str) -> List[Dict[str, Union[str, int]]]:
    """Parses the page content and extracts review data."""
    soup = BeautifulSoup(page_content, 'html.parser')
    reviews = []

    for review in soup.select('li.film-detail'):  # Adjusted CSS selector to target review containers
        try:
            rating = review.select_one('span.rating').text.strip()  # Selector for the rating
            reviewer = review.select_one('.attribution .name').text.strip()  # Selector for the reviewer name
            date = review.select_one('.attribution .date ._nobr').text.strip()  # Selector for the date
            review_link = review.select_one('.attribution .date a')['href']
            link = 'https://letterboxd.com' + review_link
            user_profile = 'https://letterboxd.com' + review.select_one('a.avatar')['href']  # Selector for the user profile link
            review_text = review.select_one('.body-text').text.strip()  # Selector for the review text
            likes = review.select_one('.like-link-target')['data-likeable-uid']  # Selector to get the unique identifier for likes

            # Forming the link to the likes page
            likes_page = 'https://letterboxd.com' + review.select_one('.like-link-target')['data-likes-page']

            review_data = {
                "reviewer": reviewer,
                "rating": rating,
                "date": date,
                "link": link,
                "user_profile": user_profile,
                "review_text": review_text,
                "likes": likes,
                "likes_page": likes_page
            }
            reviews.append(review_data)
        except AttributeError as e:
            logger.warning(f"Error in extracting data: {e}")

    return reviews

def main() -> None:
    test_cases = [
        {"film": "theater-camp", "year": "2023"},
        {"film": "bottoms"},
        {"film": "talk-to-me", "year": "2022"},
        {"film": "some-nonexistent-movie", "year": "1900"}  # This should fail gracefully
    ]

    for test_case in test_cases:
        film = test_case["film"]
        year = test_case.get("year")  # Use get method to avoid KeyError if "year" key is not present
        logger.info(f"Fetching reviews for {film} ({year})...")
        url = construct_url(film, year)
        page_content = fetch_reviews(url)
        if page_content:
            reviews = parse_review_data(page_content)
            if reviews:
                logger.info(f"Successfully fetched reviews for {film} ({year}).")
                print(json.dumps(reviews, indent=2))
            else:
                logger.warning(f"No reviews found for {film} ({year}).")
        else:
            logger.error(f"Failed to fetch reviews for {film} ({year}).")

if __name__ == "__main__":
    main()
