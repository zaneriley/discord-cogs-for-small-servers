# Seasonal Roles

> A Discord cog that automatically assigns and removes roles based on holidays and events.

## Features

- **Automatic Role Management**: Assigns and removes roles based on defined holidays
- **Holiday Banner Management**: Updates server banner for special holidays and events
- **User Opt-In/Out System**: Allows users to opt in or out of receiving seasonal roles
- **Dry Run Mode**: Test holiday role assignments without making actual changes
- **Force Holiday Command**: Manually trigger a specific holiday for special occasions

## Commands

- `/seasonal holiday add <name> <date> <color> [options]` - Add a new holiday
- `/seasonal holiday edit <name> <date> <color> [options]` - Edit an existing holiday
- `/seasonal holiday remove <name>` - Remove a holiday
- `/seasonal holiday list` - List all configured holidays
- `/seasonal member add <member>` - Add a member to the opt-in list
- `/seasonal member remove <member>` - Remove a member from the opt-in list
- `/seasonal dryrun <on/off>` - Toggle dry run mode
- `/seasonal check [date]` - Force check holidays, optionally for a specific date
- `/seasonal forceholiday <name>` - Force apply a specific holiday
- `/seasonal setbanner <url>` - Change the server banner

## Recent Improvements (v0.0.3)

- **Code Structure Refactoring**: Improved code organization with domain-driven design principles
- **Enhanced Holiday Processing**: Split complex logic into focused, single-responsibility methods
- **Better Error Handling**: Improved exception management and logging
- **Type Annotations**: Updated to use modern Python type annotation syntax
- **Reduced Complexity**: Eliminated deeply nested conditional statements for better maintainability
- **Documentation**: Added comprehensive docstrings to all methods

## Configuration

The cog comes with several pre-configured fictional holidays:

- New Year's Celebration (January 1)
- Spring Blossom Festival (March 20)
- Kids Day (May 5)
- Midsummer Festival (June 21)
- Star Festival (July 7)
- Friendship Day (August 2)
- Harvest Festival (September 22)
- Memories Festival (October 15)
- Spooky Festival (October 31)
- Winter Festival (December 21)

You can modify these or add your own custom holidays using the commands.

## Requirements

- Discord server with Manage Roles permission
- For banner features: Server must be at Boost Level 2 or higher

## Installation

```
[p]repo add discord-cogs-for-small-servers https://github.com/yourname/discord-cogs-for-small-servers
[p]cog install discord-cogs-for-small-servers seasonalroles
[p]load seasonalroles
```

Replace `[p]` with your bot's prefix. 