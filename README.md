# Discord Cogs for Small Servers

> A collection of Discord cogs designed for small, tight-knit communities (< 50 members).

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://makeapullrequest.com)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](CODE_OF_CONDUCT.md)

These cogs focus on fostering connections between friends and family in small Discord servers. While currently tailored to my specific server's style, contributions to make them more customizable are welcome!

## Available Cogs


<img src="https://github.com/zaneriley/discord-cogs-for-small-servers/blob/main/movieclub/cog-logo.png?raw=true" alt="MovieClub" width="300"/>

Schedule movie nights more easily by conducting polls and managing movie suggestions. 

**Features:**
- 🎯 Add movies to consider: `!movieclub movie add {film title}`
- 📅 Find available dates: `!movieclub poll date start`
- 🗳️ Vote on movies: `!movieclub poll movie start`
- 💬 Auto-create discussion threads: `!movieclub movie thread {film title}`

Next:
- [ ] **Event Scheduler**: Plan and coordinate Discord events, RSVPs, and send reminders.
- [ ] **Member Stats**: Track and display user activity and engagement on the server.

---
<img src="https://github.com/zaneriley/discord-cogs-for-small-servers/assets/2167062/1feb3dbe-4818-479b-a93c-2f390ad43186" alt="SeasonalRoles" width="300"/>

Automatically assign and remove roles based on specified holidays and events.

- [x] Assigns and removes roles based on defined holidays (currently semi-fictitious holidays)
- [x] Includes a way to dry run changes and force holidays, for one-offs
- [x] Allows users to opt-out of seasonal roles

---
## SocialLink (WIP)

An in-server Discord game inspired by the Persona video game series that encourages users to connect with each other. It works by lightly tracking key events (e.g., hanging out in VC channels for a while) and then assigning points to their "connection."

- [x] /confidants command to list all confidants and their scores
- [x] /journal command to view a log of events that increased links between users
- [x] /rank command to see a leaderboard of who has the deepest connections with other users

---



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

## Development

### Prerequisites

- Python 3.9+
- Docker (recommended)
- A Discord Bot Token
- Git

### Local Development

1. Set up a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # or `venv\Scripts\activate` on Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r cogs/requirements.txt
   ```

3. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

### Testing

Run tests using Docker (recommended):
```bash
docker compose up tests --build
```

Or locally:
```bash
export PYTHONPATH=./cogs
pytest
```

Run static analysis:
```bash
cd cogs
ruff .
mypy .
```

### Project Structure

```
cogs/
├── movieclub/          # Movie night coordination
├── weatherchannel/     # Weather updates and alerts
├── sociallink/         # Social game mechanics
├── emojilocker/        # Emoji management
├── utilities/          # Shared utilities
└── tests/             # Test suite
```

## Contributing

We love your input! Check out our [Contributing Guide](CONTRIBUTING.md) for guidelines on how to proceed.

### Code Style

- All Python code is formatted with `black` and checked with `ruff`
- Type hints are required and checked with `mypy`
- Pre-commit hooks ensure consistent style

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE) - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Red-DiscordBot](https://github.com/Cog-Creators/Red-DiscordBot) - Discord bot framework
- [discord.py](https://github.com/Rapptz/discord.py) - Discord API library
- [holidays](https://pypi.org/project/holidays/) - Holiday data management

---

<sub>Not affiliated with Discord Inc. or any associated entities.</sub>
