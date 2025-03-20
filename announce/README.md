# Announce

> A comprehensive announcement system for Discord servers with scheduling, templates, and rich embeds.

## Features

- **Multiple Announcement Types**: Send plain text or rich embed announcements
- **Template System**: Create, manage, and reuse announcement templates
- **Scheduling**: Schedule announcements for future dates and times
- **Recurring Announcements**: Set up daily, weekly, or monthly repeating announcements
- **Channel Management**: Designate specific channels for announcements with friendly names
- **History Tracking**: View past announcements and their details
- **Permission Controls**: Fine-grained control over who can send announcements

## Commands

### Basic Announcements

- `[p]announce text [channel] <message>` - Send a text announcement
- `[p]announce embed [channel] <title> | <description>` - Send an embed announcement

### Channel Management

- `[p]announce channel add <channel> [name]` - Add a channel to the announcement channels list
- `[p]announce channel remove <channel>` - Remove a channel from the list
- `[p]announce channel list` - List all announcement channels
- `[p]announce channel default <channel>` - Set the default announcement channel

### Templates

- `[p]announce template add <name> <content>` - Add a text announcement template
- `[p]announce template addembed <name> <title> | <description>` - Add an embed template
- `[p]announce template edit <name> <content>` - Edit a text template
- `[p]announce template editembed <name> <title> | <description>` - Edit an embed template
- `[p]announce template color <name> <color>` - Set the color for an embed template
- `[p]announce template delete <name>` - Delete a template
- `[p]announce template list` - List all templates
- `[p]announce template view <name>` - View a template's details
- `[p]announce template use <name> [channel]` - Send an announcement using a template

### Scheduling

- `[p]announce schedule text <channel> <date_time> <content>` - Schedule a text announcement
- `[p]announce schedule embed <channel> <date_time> <title> | <description>` - Schedule an embed announcement
- `[p]announce schedule template <template_name> <channel> <date_time>` - Schedule an announcement using a template
- `[p]announce schedule list` - List all scheduled announcements
- `[p]announce schedule cancel <index>` - Cancel a scheduled announcement
- `[p]announce schedule cancelall` - Cancel all scheduled announcements

### Recurring Announcements

- `[p]announce recurring add <template_name> <channel> <schedule_type> [start_time]` - Set up a recurring announcement
- `[p]announce recurring list` - List all recurring announcements
- `[p]announce recurring remove <id>` - Remove a recurring announcement

### History

- `[p]announce history list [count]` - List recent announcements
- `[p]announce history clear` - Clear the announcement history

### Permissions

- `[p]announce perm addrole <role>` - Add a role that can use announcement commands
- `[p]announce perm removerole <role>` - Remove a role's announcement permissions
- `[p]announce perm adduser <user>` - Add a user who can use announcement commands
- `[p]announce perm removeuser <user>` - Remove a user's announcement permissions
- `[p]announce perm list` - List all roles and users with announcement permissions

## Usage Examples

### Sending a Simple Announcement

```
[p]announce text #announcements Hey everyone! We'll be having server maintenance tonight at 10 PM UTC.
```

### Sending an Embed Announcement

```
[p]announce embed #announcements Server Maintenance | We'll be having server maintenance tonight from 10 PM to 11 PM UTC. The bot will be offline during this period.
```

### Creating and Using a Template

```
[p]announce template add maintenance Server maintenance will take place on {date} at {time}. Please be patient during this time.

[p]announce template use maintenance #announcements
```

### Scheduling an Announcement

```
[p]announce schedule text #announcements 2023-12-25 08:00 Merry Christmas everyone! Hope you have a wonderful day.
```

### Setting Up a Recurring Announcement

```
[p]announce template add weekly_reminder It's time for our weekly community game night! Join us in the voice channel at 8 PM.

[p]announce recurring add weekly_reminder #announcements weekly 2023-07-01 20:00
```

## Configuration

Administrators can configure the following aspects:

1. **Announcement Channels**: Designate which channels can be used for announcements
2. **Default Channel**: Set a default channel for announcements
3. **Permissions**: Control which roles and users can send announcements
4. **Templates**: Create and manage reusable announcement templates
5. **Scheduled Announcements**: View and manage scheduled announcements

## Requirements

- Discord server with appropriate permissions
- RedBot v3.5.0 or higher
- Bot must have permissions to:
  - Send messages in designated announcement channels
  - Embed links (for embed announcements)
  - Manage messages (optional, for editing announcements)

## Installation

```
[p]repo add discord-cogs-for-small-servers https://github.com/yourname/discord-cogs-for-small-servers
[p]cog install discord-cogs-for-small-servers announce
[p]load announce
```

Replace `[p]` with your bot's prefix. 