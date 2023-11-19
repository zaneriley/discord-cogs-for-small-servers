import logging
import os
import json
from dotenv import load_dotenv
from typing import Dict, Any, Union, Optional, List
from operator import itemgetter

import discord
from discord import ui, Embed

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), "../../../.env"))

from .tmdb import fetch_movie_details as fetch_tmdb_details
from .letterboxd import fetch_letterboxd_details_wrapper as fetch_letterboxd_details
from .letterboxd import construct_url, fetch_reviews, parse_review_data


# Configure logging
logging.basicConfig(level=logging.INFO)


def fetch_and_normalize_movie_data(movie_name: str) -> Dict[str, Union[str, Any]]:
    try:
        logging.info(f"Fetching movie data for: {movie_name}")

        # Fetch data from TMDB
        tmdb_details = fetch_tmdb_details(movie_name)

        # Fetch data from Letterboxd
        letterboxd_details = fetch_letterboxd_details(movie_name)
        logging.info(f"Letterboxd details: {letterboxd_details}")
        if "letterboxd_link" in letterboxd_details:
            # Fetch Reviews
            review_url = construct_url(letterboxd_details["letterboxd_link"], "reviews")
            review_page_content = fetch_reviews(review_url)
            reviews = (
                parse_review_data(review_page_content) if review_page_content else None
            )
        else:
            reviews = None

        # Map data in our specific format and merge it
        movie_data: Dict[str, Union[str, Any]] = {
            "title": letterboxd_details.get("title", "")
            or tmdb_details.get("title", ""),
            "year_of_release": letterboxd_details.get("year_of_release", "")
            or tmdb_details.get("year_of_release", ""),
            "tagline": letterboxd_details.get("tagline", "")
            or tmdb_details.get("tagline", ""),
            "description": letterboxd_details.get("description", "")
            or tmdb_details.get("description", ""),
            "genre": letterboxd_details.get("genres", [])
            or tmdb_details.get("genres", []),
            "runtime": letterboxd_details.get("runtime", 0)
            or tmdb_details.get("runtime", 0),
            "rating": letterboxd_details.get("average_rating", "N/A"),
            "reviews": reviews,
            "number_of_reviewers": letterboxd_details.get("number_of_reviewers", 0),
            "trailer_url": letterboxd_details.get("trailer_link", "")
            or tmdb_details.get("trailer_link", ""),
            "letterboxd_link": letterboxd_details.get("letterboxd_link", ""),
            "banner_image": letterboxd_details.get("banner_image", ""),
        }

        logging.info("Fetched and normalized movie data.")
        return movie_data
    except Exception as e:
        logging.error(f"Error while fetching movie data: {e}", exc_info=True)
        raise


def select_review(reviews: List[Dict[str, Union[str, Any]]]) -> Optional[str]:
    # Select the most popular review with less than 140 characters.
    if reviews:
        for review in reviews:
            if "review_text" in review and len(review["review_text"]) < 140:
                return review["review_text"]
    return None


def convert_to_presentable_count(number: int) -> str:
    """
    Takes a number and convert it into K, M, B, etc. based on its size
    """
    if number is None:
        logging.error("Number is None")
        return "N/A"
    elif number > 1_000_000_000:
        return f"{number/1_000_000_000:.1f}B"
    elif number > 1_000_000:
        return f"{number/1_000_000:.1f}M"
    elif number > 1_000:
        return f"{number/1_000:.1f}K"
    else:
        return str(number)


def movie_data_to_discord_format(movie_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        logging.info("Formatting movie data to Discord message format.")

        tagline = movie_data.get("tagline")
        description_text = movie_data.get("description", "")

        description = f"`{tagline.upper() if tagline else 'No tagline available'}`\n\n{description_text}"

        author_value = "TODO"  # Value derived from movie_data, hard-coded or from an external source
        fields = [
            {
                "name": "Details",
                "value": f"{', '.join(movie_data['genre'][:2])} · {movie_data['runtime']} mins",
                "inline": True,
            },
            {
                "name": "Rating",
                "value": f"★ {movie_data['rating']} · {convert_to_presentable_count(movie_data['number_of_reviewers'])} fans",
                "inline": True,
            },
            {
                "name": "More",
                "value": f"[Trailer]({movie_data['trailer_url']}) · [Letterboxd]({movie_data['letterboxd_link']})",
                "inline": True,
            },
        ]

        # Create the Embed object
        embed = discord.Embed(
            title=f"{movie_data['title']} ({movie_data.get('year_of_release', '')})",
            description=description,
            color=3356474,
        )

        # Add fields using the add_field method
        for field in fields:
            embed.add_field(
                name=field["name"], value=field["value"], inline=field["inline"]
            )

        banner_image = movie_data.get("banner_image")
        if banner_image:
            embed.set_image(url=banner_image)

        footer_text = select_review(movie_data.get("reviews", []))

        if footer_text:
            footer_text = f'"{footer_text}"'
            footer_icon = "https://cdn3.emoji.gg/emojis/7133-star.gif"
            embed.set_footer(text=footer_text, icon_url=footer_icon)

        return embed
    except Exception as e:
        logging.error(
            f"Error in mapping movie data to discord format: {e}", exc_info=True
        )
        raise


def get_movie_discord_embed(movie_name: str) -> Dict[str, Any]:
    try:
        movie_data = fetch_and_normalize_movie_data(movie_name)
        if movie_data:
            discord_format = movie_data_to_discord_format(movie_data)
            if discord_format:
                logging.info(f"Generated Discord message for {movie_name}.")
                logging.info(f"Discord message: {discord_format}")
                return movie_data, discord_format
        else:
            raise Exception(f"Failed to fetch movie data for {movie_name}.")
    except Exception as e:
        logging.error(f"An error occurred in gather_movie_info: {e}", exc_info=True)
        return {}
