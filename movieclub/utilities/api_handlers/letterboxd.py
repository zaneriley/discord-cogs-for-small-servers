import requests
from bs4 import BeautifulSoup
import json
import logging
from typing import List, Dict, Union, Optional
import unicodedata
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from typing import Optional

def get_validated_base_url(film: str, year: Optional[str] = None) -> str:
    base_url = f"https://letterboxd.com/film/{film}"
    url_with_year = f"{base_url}-{year}" if year else None
    url_without_year = base_url

    if url_with_year:
        response = requests.get(url_with_year)
        if response.status_code == 200:
            return url_with_year
        elif response.status_code == 404:
            response = requests.get(url_without_year)
            if response.status_code == 200:
                return url_without_year

    else:
        response = requests.get(url_without_year)
        if response.status_code == 200:
            return url_without_year

    raise ValueError(f"Invalid movie or year: {response.status_code} {response.reason} for URL: {response.url}")

def construct_url(base_url: str, url_type: str) -> str:
    if url_type == 'info':
        return f"{base_url}/"
    elif url_type == 'reviews':
        return f"{base_url}/reviews/by/activity/"
    elif url_type == 'stats':
        return f"{base_url}/likes/"
    else:
        raise ValueError(f"Invalid url_type: {url_type}. Expected 'info', 'reviews', or 'stats'.")

def fetch_reviews(url: str) -> Optional[str]:
    """Fetches the reviews from the constructed URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch reviews: {e}")
        return None

def parse_review_data(page_content: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(page_content, 'html.parser')
    reviews = []

    for review in soup.select('li.film-detail'):
        reviewer = review.select_one('strong.name')
        reviewer = unicodedata.normalize("NFC", reviewer.get_text()) if reviewer else "Unknown"
        
        rating = review.select_one('.rating')
        rating = unicodedata.normalize("NFC", rating.get_text()) if rating else "No rating"

        date = review.select_one('span._nobr')
        date = date.get_text() if date else "Unknown date"

        # Fetching individual paragraphs and joining them with newline characters
        review_text_section = review.select_one('.body-text')
        review_text = ""
        if review_text_section:
            paragraphs = review_text_section.select('p')
            review_text = "\n".join([p.get_text() for p in paragraphs])
        
        link = review.find('a', class_='context')['href']
        link = f"https://letterboxd.com{link}" if link else "No link"

        user_profile_link = review.find('a', class_='avatar')['href']
        user_profile_link = f"https://letterboxd.com{user_profile_link}" if user_profile_link else "No link"

        likes = review.find('p', class_='like-link-target')
        likes = likes['data-likes-page'] if likes else "No likes data"

        reviews.append({
            "reviewer": reviewer,
            "rating": rating,
            "date": date,
            "link": link,
            "user_profile": user_profile_link,
            "review_text": review_text,
            "likes": likes
        })
    
    return reviews


def fetch_movie_data(film: str, year: str = None):
    url_with_year = construct_url(film, 'info')
    url_without_year = construct_url(film, 'info')

    response = requests.get(url_with_year)
    if response.status_code == 404:
        response = requests.get(url_without_year)
    
    if response.status_code == 200:
        try:
            url = response.url  # Capture the correct URL from the response
            soup = BeautifulSoup(response.content, 'html.parser')

            # Get the necessary data
            title_section = soup.find('section', {'id': 'featured-film-header'})
            title = title_section.find('h1', class_='headline-1').get_text() if title_section else None

            year_of_release = soup.find('small', class_='number').find('a').text if soup.find('small', class_='number') else None
            tagline = soup.find('h4', class_='tagline').text if soup.find('h4', class_='tagline') else None
            description = soup.find('div', class_='truncate').find('p').text if soup.find('div', class_='truncate') else None
            genres = [a.text for a in soup.find('div', id='tab-genres').find('div', class_='text-sluglist capitalize').find_all('a', class_='text-slug')] if soup.find('div', id='tab-genres') else None  
            
            runtime_paragraph = soup.find('p', class_='text-link text-footer')
            if runtime_paragraph:
                runtime_text = runtime_paragraph.get_text()
                runtime_match = re.search(r'(\d+)\s*mins', runtime_text)
                if runtime_match:
                    runtime = int(runtime_match.group(1).replace(',', ''))  # Convert to integer after removing any commas
                else:
                    runtime = None
            else:
                runtime = None

            trailer_link_section = soup.find('p', class_='trailer-link js-watch-panel-trailer')
            if trailer_link_section:
                trailer_link_a = trailer_link_section.find('a')
                if trailer_link_a and trailer_link_a.has_attr('href'):
                    trailer_link = "https:" + trailer_link_a['href']
                else:
                    trailer_link = None
            else:
                trailer_link = None
            # Get the ratings
            script_tag = soup.find('script', type='application/ld+json')
            if script_tag:
                script_text = script_tag.string
                clean_script_text = script_text.replace("/* <![CDATA[ */", "").replace("/* ]]> */", "")
                script_json = json.loads(clean_script_text)
                aggregate_rating = script_json.get('aggregateRating', {})
                average_rating = aggregate_rating.get('ratingValue')
                number_of_reviewers = aggregate_rating.get('reviewCount') or aggregate_rating.get('ratingCount')
            else:
                average_rating = None
                number_of_reviewers = None

            # Step 3: Data Parsing
            movie_data = {
                "title": title,
                "year_of_release": year_of_release,
                "description": description,
                "tagline": tagline,
                "genres": genres,
                "runtime": runtime,
                "average_rating": average_rating,
                "number_of_reviewers": number_of_reviewers,
                "trailer_link": trailer_link,
                "letterboxd_link": url,
            }
                
            return movie_data

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch data for {film} ({year}) due to: {str(e)}")
            return None

       
    else:
        logger.error(f"Failed to fetch data for {film} ({year}) due to: {response.status_code} {response.reason} for url: {response.url}")
        return None, None


def main() -> None:
    test_cases = [
        {"film": "the-great-escape", "year": "1963"},
        {"film": "surf-ninjas"},
        {"film": "the-adventures-of-buckaroo-banzai-across-the-8th-dimension", "year": "1987"},
    ]

    for test_case in test_cases:
        film = test_case["film"]
        year = test_case.get("year")  # Use get method to avoid KeyError if "year" key is not present

        try:
            base_url = get_validated_base_url(film, year)
            
            # Fetching and logging movie data
            logger.info(f"Fetching data for {film} ({year})...")
            movie_data_url = construct_url(base_url, 'info')
            movie_data = fetch_movie_data(movie_data_url)
            if movie_data:
                logger.info(f"Successfully fetched data for {film} ({year}).")
                print(json.dumps(movie_data, indent=2))
            else:
                logger.error(f"Failed to fetch data for {film} ({year}).")

            # Fetching and logging reviews
            logger.info(f"Fetching reviews for {film} ({year})...")
            review_url = construct_url(base_url, 'reviews')
            page_content = fetch_reviews(review_url)
            if page_content:
                reviews = parse_review_data(page_content)
                if reviews:
                    logger.info(f"Successfully fetched reviews for {film} ({year}).")
                    print(json.dumps(reviews, indent=2))
                else:
                    logger.warning(f"No reviews found for {film} ({year}).")
            else:
                logger.error(f"Failed to fetch reviews for {film} ({year}).")

        except ValueError as e:
            logger.error(f"Failed to fetch data for {film} ({year}) due to: {str(e)}")

if __name__ == "__main__":
    main()