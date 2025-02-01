# Discord Cogs for Small Servers

This repository contains a collection of Discord cogs tailored for smaller server communities, particularly those with less than 50 members. These cogs focus on getting people (e.g., friends, family) to connect.

**Heads up:** These cogs are currently built for my particular servers and style (e.g., response messages), but I welcome any PRs if you'd like to generalize/customize them for your server.

## Features

<img src="https://github.com/zaneriley/discord-cogs-for-small-servers/blob/main/movieclub/cog-logo.png?raw=true" alt="MovieClub" width="300"/>

Schedule movie nights more easily by conducting polls and managing movie suggestions. 

- [x] Add movies to consider with `!movieclub movie add {film title}`. This will automatically pull info from TMDB and Letterboxd and load it into the next poll.
- [x] Decide on a date with `!movieclub poll date start` which will find available dates at the end of the month. It even accounts for (US) holidays.
- [x] Choose a movie with `!movieclub poll movie start` which loads all suggested movies into a poll for a vote.
- [X] **Movie journal**: Automatically create a forum channel with each film, allowing users to discuss the movie afterward. You can also make one manually by doing `!movieclub movie thread {film title}`

Next:
- [ ] **Event Scheduler**: Plan and coordinate Discord events, RSVPs, and send reminders.
- [ ] **Member Stats**: Track and display user activity and engagement on the server.

<img src="https://github.com/zaneriley/discord-cogs-for-small-servers/assets/2167062/1feb3dbe-4818-479b-a93c-2f390ad43186" alt="SeasonalRoles" width="300"/>

Automatically assign and remove roles based on specified holidays and events.

- [x] Assigns and removes roles based on defined holidays (currently semi-fictitious holidays)
- [x] Includes a way to dry run changes and force holidays, for one-offs
- [x] Allows users to opt-out of seasonal roles

## SocialLink (WIP)

An in-server Discord game inspired by the Persona video game series that encourages users to connect with each other. It works by lightly tracking key events (e.g., hanging out in VC channels for a while) and then assigning points to their "connection."

- [x] /confidants command to list all confidants and their scores
- [x] /journal command to view a log of events that increased links between users
- [x] /rank command to see a leaderboard of who has the deepest connections with other users

## WeatherChannel

<img src="https://github.com/zaneriley/discord-cogs-for-small-servers/blob/main/weatherchannel/cog-logo.png?raw=true" alt="WeatherChannel" width="300"/>

A simple command to display users' local weather together at a specific time. Currently, you'll need to load the locations in a `.env` file like:

```bash
WX_LOCATIONS={"San Francisco": ["weather-gov", "37.7749,-122.4194"], "New York City": ["weather-gov", "40.730610,-73.935242"]}
```

- [x] **Fetch Weather Data**: Retrieve weather forecasts from the WeatherGovAPI.
- [x] **Display Weather Information**: Show current weather for individual or all default locations using `!weather today [location]`.
- [x] **Set Weather Channel**: Designate which channel to post weather updates in.
- [x] **Scheduled Updates**: Automatically post daily weather updates at 6 AM Eastern Time.

Next:
- [ ] **Weather Alerts**: Incorporate weather alerts into the daily updates.
- [ ] **User Customization**: Allow users to customize their preferred weather information and notification settings.
- [ ] **Support Additional APIs**: Expand support to include more weather data sources for increased reliability and feature diversity.

## EmojiLocker

<img src="https://github.com/zaneriley/discord-cogs-for-small-servers/blob/main/emojilocker/cog-logo.png?raw=true" alt="EmojiLocker" width="300"/>

Keep your server's custom emojis organized and exclusive by controlling which roles can use them. Perfect for creating VIP perks or managing themed channels.

- [x] **Easy Emoji Creation**: Add new emojis by simply pasting an image URL, uploading a file, or copying from other servers with `!emojilocker create {name} {source}`.
- [x] **Role-Based Access**: Restrict multiple emojis to specific roles (e.g., VIP members, event participants) with `!emojilocker set {emoji1} {emoji2} ...`.
- [x] **Remove Restrictions**: Unrestrict emojis to allow all roles to use them with `!emojilocker unset`.
- [x] **Bulk Management**: View and manage all restricted emojis in one place with `!emojilocker list`.
- [x] **Admin Override**: Admins always retain access to restricted emojis.


## Installation

Follow these steps to set up your development environment:

**Step 1: Clone the Repository**

Clone this repository to your local machine:

```bash
git clone git@github.com:zaneriley/discord-cogs-for-small-servers.git
```

Create an .env file with:

```
DISCORD_BOT_TOKEN=01234567890
GUILD_ID=12345678901234567890 # Right-click your server icon and hit "copy server ID"
```

## Contributing

Contributions are welcome! If you find any issues or have ideas for improvements, please create an issue or submit a pull request.

## License

This project is licensed under the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html). This ensures the freedom to use, modify, and distribute, but requires any derivative works or distributions to be open-source under the same license. See the [LICENSE](LICENSE) file in this repository for more details.

## Acknowledgements

- [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot): An extensible, customizable Discord bot framework.
- [discord.py](https://github.com/Rapptz/discord.py): A powerful library for interacting with the Discord API.
- [holidays](https://pypi.org/project/holidays/): A Python library for generating and managing public holidays.

## Disclaimer

This project is not affiliated with or endorsed by Discord or any associated entities.
