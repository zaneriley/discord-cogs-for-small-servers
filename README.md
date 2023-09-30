# Discord Cogs for Small Servers

This repository contains a collection of Discord cogs tailored for smaller server communities, particularly those with less than 50 members These cogs focus on getting people (e.g. friends, family) to connect. 

**heads up:** These cogs are currently built for my particular servers and style (e.g. response messages), but I welcome any PRs if you'd like to generalize/customize them for your server.


## Features

![MovieClub](https://github.com/zaneriley/discord-cogs-for-small-servers/blob/main/movieclub/cog-logo.png?raw=true)

Schedule movie nights more easily by conducting polls and managing movie suggestions. 

- [x] Add movies to consider with `!movieclub movie add {film title}`. This will automatically pull info from TMDB and Letterboxd and load it into the next poll.
- [x] Decide on a date with `!movieclub poll date start` which will find available dates at the end of the month. It even accounts for (US) holidays.
- [x] Choose a movie with `!movieclub poll movie start` which loads all suggest movies into a poll for a vote.
- [X] **Movie journal**: Automatically create a forum channel with each film, allowing users to discuss the movie afterward. You can also make one manually by doing `!movieclub movie thread {film title}`

Next:
- [ ] **Event Scheduler**: Plan and coordinate discord events, RSVPs, and send reminders. 

- [ ] **Member Stats**: Track and display user activity and engagement on the server.

## Requirements

To use these cogs, you need the following:

- **Python 3.8+**
- **Discord.py**
- **Red-DiscordBot**

## Installation

Follow these steps to set up your development environment:

**Step 1: Clone the Repository**

Clone this repository to your local machine:

```bash
git clone git@github.com:zaneriley/discord-cogs-for-small-servers.git
```

TBD

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