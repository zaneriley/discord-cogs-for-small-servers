from __future__ import annotations

import logging
import os
from typing import Any

import aiohttp
import discord
from dotenv import load_dotenv

from movieclub.api_handlers.letterboxd import (
    construct_url,
    fetch_reviews,
    parse_review_data,
)
from movieclub.api_handlers.letterboxd import (
    fetch_letterboxd_details_wrapper as fetch_letterboxd_details,
)
from movieclub.api_handlers.tmdb import fetch_movie_details as fetch_tmdb_details

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), "../../../.env"))


# Configure logging
logging.basicConfig(level=logging.INFO)


class MovieDataFetcher:
    def __init__(self):
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch_movie_info(self, movie_name: str):
        try:
            async with self:
                logging.info(f"Fetching movie data for: {movie_name}")

                tmdb_details = fetch_tmdb_details(movie_name)

                letterboxd_details = fetch_letterboxd_details(movie_name)
                logging.info(f"Letterboxd details: {letterboxd_details}")
                if "letterboxd_link" in letterboxd_details:
                    review_url = construct_url(letterboxd_details["letterboxd_link"], "reviews")
                    review_page_content = fetch_reviews(review_url)
                    reviews = parse_review_data(review_page_content) if review_page_content else None
                else:
                    reviews = None

                movie_data: dict[str, str | Any] = {
                    "title": letterboxd_details.get("title", "") or tmdb_details.get("title", ""),
                    "year_of_release": letterboxd_details.get("year_of_release", "") or tmdb_details.get("year_of_release", ""),
                    "tagline": letterboxd_details.get("tagline", "") or tmdb_details.get("tagline", ""),
                    "description": letterboxd_details.get("description", "") or tmdb_details.get("description", ""),
                    "genre": letterboxd_details.get("genres", []) or tmdb_details.get("genres", []),
                    "runtime": letterboxd_details.get("runtime", 0) or tmdb_details.get("runtime", 0),
                    "rating": letterboxd_details.get("average_rating", "N/A"),
                    "reviews": reviews,
                    "number_of_reviewers": letterboxd_details.get("number_of_reviewers", 0),
                    "trailer_url": letterboxd_details.get("trailer_link", "") or tmdb_details.get("trailer_link", ""),
                    "letterboxd_link": letterboxd_details.get("letterboxd_link", ""),
                    "banner_image": letterboxd_details.get("banner_image", ""),
                }

                logging.info("Fetched and normalized movie data.")
                return movie_data
        except Exception as e:
            error_msg = f"Error in fetch_movie_info for {movie_name}: {e}"
            logging.error(error_msg, exc_info=True)
            return None, None


def select_review(reviews: list[dict[str, str | Any]]) -> str | None:
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
    if number > 1_000_000_000:
        return f"{number/1_000_000_000:.1f}B"
    if number > 1_000_000:
        return f"{number/1_000_000:.1f}M"
    if number > 1_000:
        return f"{number/1_000:.1f}K"
    return str(number)


def movie_data_to_discord_format(movie_data: dict[str, Any]) -> dict[str, Any]:
    try:
        logging.info("Formatting movie data to Discord message format.")

        tagline = movie_data.get("tagline")
        description_text = movie_data.get("description", "")

        description = f"`{tagline.upper() if tagline else 'No tagline available'}`\n\n{description_text}"

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

        embed = discord.Embed(
            title=f"{movie_data['title']} ({movie_data.get('year_of_release', '')})",
            description=description,
            color=3356474,
        )

        for field in fields:
            embed.add_field(name=field["name"], value=field["value"], inline=field["inline"])

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
        logging.error(f"Error in mapping movie data to discord format: {e}", exc_info=True)
        raise


def get_movie_discord_embed(movie_name: str) -> dict[str, Any]:
    try:
        movie_data, discord_format = asyncio.run(MovieDataFetcher().fetch_movie_info(movie_name))
        if movie_data:
            discord_format = movie_data_to_discord_format(movie_data)
            if discord_format:
                logging.info(f"Generated Discord message for {movie_name}.")
                logging.info(f"Discord message: {discord_format}")
                return movie_data, discord_format
        else:
            msg = f"Failed to fetch movie data for {movie_name}."
            raise Exception(msg)
    except Exception as e:
        logging.error(f"An error occurred in gather_movie_info: {e}", exc_info=True)
        return {}
