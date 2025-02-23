from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Any
from urllib.parse import quote, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def construct_search_url(movie_title: str) -> str:
    try:
        logging.info(f"Constructing search URL for {movie_title}...")

        # quote function will encode our string into URL encoding format
        # replace function will ensure that spaces are replaced with plus symbols
        movie_title_encoded = quote(movie_title).replace(" ", "+")

        search_url = f"https://letterboxd.com/search/{movie_title_encoded}/"
        logging.info(f"Successfully constructed search URL for {search_url}.")
        return search_url
    except Exception as e:
        logger.exception(f"Failed to construct the search URL for {movie_title} due to: {e!s}")
        return None


def scrape_search_page(search_url: str) -> BeautifulSoup | None:
    try:
        response = requests.get(search_url)
        response.raise_for_status()
        return BeautifulSoup(response.content, "html.parser")
    except requests.exceptions.RequestException as e:
        logger.exception(f"Failed to fetch search page: {e}")
        return None


def fetch_search_results(movie_title: str) -> list[BeautifulSoup]:
    try:
        search_url = construct_search_url(movie_title)
        soup = scrape_search_page(search_url)
        results = soup.find_all("li") if soup else []
        if results:
            logger.info(f"Successfully fetched {len(results)} search results for {movie_title}.")
            logger.info(f"First result content: {results[0].prettify() if results else 'None'}")
        else:
            logger.warning(f"No search results found for {movie_title}.")
        return results
    except Exception as e:
        logger.exception(f"Failed to fetch search results for {movie_title} due to: {e!s}")
        return []


def select_best_search_result(search_results: list[BeautifulSoup], film: str) -> str:
    try:
        film = film.lower()
        # Check each search result
        for result in search_results:
            title_element = result.select_one("span.film-title-wrapper > a")

            if title_element:
                # Get movie title excluding the 'small' tag (year)
                title = "".join(title_element.find_all(text=True, recursive=False)).strip().lower()
                logger.info(f"Scraped title: {title}")
                url = title_element.get("href", "")
                url = f"https://letterboxd.com{url}"
                logger.info(
                    f"Search input keyword and found title doesn't match. Title scraped: {title}, Movie title input: {film}"
                )
                logger.info(f"Going with best match found: {title}")
                return url

        logger.error(f"No suitable results found for film: {film}")
        return None
    except Exception as e:
        logger.exception(f"Failed to select best search result due to: {e!s}")
        return None


def get_validated_base_url(film: str, year: str | None = None) -> str:
    film = film.lower()
    base_url = f"https://letterboxd.com/film/{film}"
    url_with_year = f"{base_url}-{year}" if year else None
    url_without_year = base_url

    if url_with_year:
        response = requests.get(url_with_year)
        if response.status_code == 200:
            return url_with_year
        if response.status_code == 404:
            response = requests.get(url_without_year)
            if response.status_code == 200:
                return url_without_year

    else:
        response = requests.get(url_without_year)
        if response.status_code == 200:
            return url_without_year

    msg = f"Invalid movie or year: {response.status_code} {response.reason} for URL: {response.url}"
    raise ValueError(msg)


def construct_url(base_url: str, url_type: str) -> str:
    if url_type == "info":
        return f"{base_url}"
    if url_type == "reviews":
        return f"{base_url}/reviews/by/activity/"
    if url_type == "stats":
        return f"{base_url}/likes/"
    msg = f"Invalid url_type: {url_type}. Expected 'info', 'reviews', or 'stats'."
    raise ValueError(msg)


def fetch_reviews(url: str) -> str | None:
    """Fetches the reviews from the constructed URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.exception(f"Failed to fetch reviews: {e}")
        return None


def parse_review_data(page_content: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(page_content, "html.parser")
    reviews = []
    for review in soup.select("li.film-detail"):
        reviewer = review.select_one("strong.name")
        reviewer = unicodedata.normalize("NFC", reviewer.get_text()) if reviewer else "Unknown"
        rating = review.select_one(".rating")
        rating = unicodedata.normalize("NFC", rating.get_text()) if rating else "No rating"
        date = review.select_one("span._nobr")
        date = date.get_text() if date else "Unknown date"
        # Fetching individual paragraphs and joining them with newline characters
        review_text_section = review.select_one(".body-text")
        review_text = ""
        if review_text_section:
            paragraphs = review_text_section.select("p")
            review_text = "\n".join([p.get_text() for p in paragraphs])
        link = review.find("a", class_="context")["href"]
        link = f"https://letterboxd.com{link}" if link else "No link"
        user_profile_link = review.find("a", class_="avatar")["href"]
        user_profile_link = f"https://letterboxd.com{user_profile_link}" if user_profile_link else "No link"

        # Remove json of likes from reviews
        reviews.append(
            {
                "reviewer": reviewer,
                "rating": rating,
                "date": date,
                "link": link,
                "user_profile": user_profile_link,
                "review_text": review_text,
            }
        )
    return reviews


def fetch_movie_details(film: str, year: str | None = None):
    film = film.lower()
    url_with_year = construct_url(film, "info")
    url_without_year = construct_url(film, "info")

    response = requests.get(url_with_year)
    if response.status_code == 404:
        response = requests.get(url_without_year)

    if response.status_code == 200:
        try:
            url = response.url  # Capture the correct URL from the response
            parsed_url = urlparse(url)
            cleaned_path = "/".join(segment for segment in parsed_url.path.split("/") if segment)
            url = urlunparse(parsed_url._replace(path=cleaned_path))

            soup = BeautifulSoup(response.content, "html.parser")

            # Get the necessary data
            title_section = soup.find("section", {"id": "featured-film-header"})
            title = title_section.find("h1", class_="headline-1").get_text() if title_section else None

            year_of_release = (
                soup.find("small", class_="number").find("a").text if soup.find("small", class_="number") else None
            )
            tagline = soup.find("h4", class_="tagline").text if soup.find("h4", class_="tagline") else None
            description = (
                soup.find("div", class_="truncate").find("p").text if soup.find("div", class_="truncate") else None
            )
            genres = (
                [
                    a.text
                    for a in soup.find("div", id="tab-genres")
                    .find("div", class_="text-sluglist capitalize")
                    .find_all("a", class_="text-slug")
                ]
                if soup.find("div", id="tab-genres")
                else None
            )

            runtime_paragraph = soup.find("p", class_="text-link text-footer")
            if runtime_paragraph:
                runtime_text = runtime_paragraph.get_text()
                runtime_match = re.search(r"(\d+)\s*mins", runtime_text)
                if runtime_match:
                    runtime = int(
                        runtime_match.group(1).replace(",", "")
                    )  # Convert to integer after removing any commas
                else:
                    runtime = None
            else:
                runtime = None

            trailer_link_section = soup.find("p", class_="trailer-link js-watch-panel-trailer")
            if trailer_link_section:
                trailer_link_a = trailer_link_section.find("a")
                if trailer_link_a and trailer_link_a.has_attr("href"):
                    trailer_link = trailer_link_a["href"]
                    if trailer_link.startswith("//"):
                        trailer_link = "https:" + trailer_link
                else:
                    trailer_link = None
            else:
                trailer_link = None

            # Extract the backdrop image URL
            backdrop_div = soup.find("div", id="backdrop")
            if backdrop_div and backdrop_div.has_attr("data-backdrop"):
                image_url = backdrop_div["data-backdrop"]
            else:
                image_url = None

            # Get the ratings
            script_tag = soup.find("script", type="application/ld+json")
            if script_tag:
                script_text = script_tag.string
                clean_script_text = script_text.replace("/* <![CDATA[ */", "").replace("/* ]]> */", "")
                script_json = json.loads(clean_script_text)
                aggregate_rating = script_json.get("aggregateRating", {})
                average_rating = aggregate_rating.get("ratingValue")
                number_of_reviewers = aggregate_rating.get("reviewCount") or aggregate_rating.get("ratingCount")
            else:
                average_rating = None
                number_of_reviewers = None

            # Step 3: Data Parsing
            return {
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
                "banner_image": image_url,
            }


        except requests.exceptions.RequestException as e:
            logger.exception(f"Failed to fetch data for {film} ({year}) due to: {e!s}")
            return None

    else:
        logger.error(
            f"Failed to fetch data for {film} ({year}) due to: {response.status_code} {response.reason} for url: {response.url}"
        )
        return None, None


def fetch_letterboxd_details_wrapper(film: str) -> dict[str, str | Any]:
    try:
        logger.info(f"Fetching search results for {film} on Letterboxd...")
        results = fetch_search_results(film)

        if not results:
            logger.error(f"No search results found for {film}.")
            return {}

        selected_url = select_best_search_result(results, film)
        if not selected_url:
            logger.warning(f"No suitable match found for {film}. There are no exact matches in the search results.")
            return {}

        movie_data = fetch_movie_details(selected_url)

        if movie_data:
            logger.info(f"Successfully fetched and parsed movie data for {film}.")
            return movie_data
        logger.error(f"Failed to fetch and parse data for {film}.")
        return {}
    except (
        requests.RequestException,
        Exception,
    ) as e:  # Catch and log possible network and parsing errors
        logger.exception(f"An error occurred while fetching movie details for {film}: {e!s}")
        return {}


def main() -> None:
    test_cases = [
        {"film": "The Great Escape", "year": "1963"},
        {"film": "Surf Ninjas"},
        {
            "film": "The Adventures of Buckaroo Banzai Across the 8th Dimension",
            "year": "1987",
        },
        {"film": "Love on a Leash"},
        {"film": "10½"},
    ]
    for test_case in test_cases:
        film = test_case["film"]
        year = test_case.get("year")  # Use get method to avoid KeyError if "year" key is not present
        try:
            # Fetching search results and selecting the best match
            logger.info(f"Fetching search results for {film} ({year if year else ''})...")
            results = fetch_search_results(film)

            if results:
                selected_url = select_best_search_result(results, film)
                if selected_url is not None:
                    # Fetching and logging movie data
                    logger.info(f"Fetching data for {film} ({year if year else ''})...")
                    movie_data = fetch_movie_details(selected_url)
                    if movie_data:
                        logger.info(f"Successfully fetched data for {film} ({year if year else ''}).")
                    else:
                        logger.error(f"Failed to fetch data for {film} ({year if year else ''}).")
                    # Fetching and logging reviews
                    logger.info(f"Fetching reviews for {film} ({year if year else ''})...")
                    review_url = construct_url(selected_url, "reviews")
                    page_content = fetch_reviews(review_url)
                    if page_content:
                        reviews = parse_review_data(page_content)
                        if reviews:
                            logger.info(f"Successfully fetched reviews for {film} ({year if year else ''}).")
                        else:
                            logger.warning(f"No reviews found for {film} ({year if year else ''}).")
                    else:
                        logger.error(f"Failed to fetch reviews for {film} ({year if year else ''}).")
                else:
                    logger.error(f"No suitable search result selected for {film} ({year if year else ''}).")
                    continue
            else:
                logger.error(f"Failed to fetch search results for {film} ({year if year else ''}).")
                continue
        except ValueError as e:
            logger.exception(f"Failed to process {film} ({year if year else ''}) due to: {e!s}")


if __name__ == "__main__":
    main()
