# Seasonal Roles Holiday Announcement - Implementation Plan

## Base Announcement Utility

- [x] Modify `utilities/announcement_utils.py` to extend existing functionality
- [x] Create wrapper for `discord_utils.send_discord_message()` to support holiday announcements
- [x] Implement enhanced embed creation that builds on existing Discord utilities
- [x] Add holiday-specific styling to embeds (colors, thumbnails matching the holiday)
- [x] Create mention handling that leverages existing Discord utilities
- [x] **LINT CHECK**: Run `docker-compose run lint` to verify code quality
- [x] Implement validation that uses `discord_utils` permission checking
- [x] Develop error handling and logging consistent with other utilities
- [x] Add rate limit protection using existing patterns from `discord_utils`
- [x] Create holiday announcement method that integrates all components
- [x] Implement preview functionality for testing announcements
- [x] **LINT CHECK**: Run `docker-compose run lint` to verify code quality
- [x] Add unit tests for new announcement functionality

## Holiday Announcer Service

- [x] Create `cogs/seasonalroles/holiday_announcer.py` basic class structure
- [x] Define default message templates for different holiday phases (before, during, after)
- [x] Implement `get_holiday_message()` to retrieve the appropriate template
- [x] **LINT CHECK**: Run `docker-compose run lint` to verify code quality
- [x] Create `announce_upcoming_holiday()` method for 7-day announcements
- [x] Implement `announce_holiday_start()` method for day-of announcements
- [x] Develop `announce_holiday_end()` method for day-after announcements
- [x] Add color selection method based on holiday theme
- [x] **LINT CHECK**: Run `docker-compose run lint` to verify code quality
- [ ] Create message customization functionality for server-specific templates
- [ ] Implement fallback templates for holidays without custom messages
- [x] Add method to check if an announcement was already sent for a specific phase

## Configuration Management

### Base Configuration Schema
- [x] Define `announcement_config` structure with toggle, channel, and mention settings
- [x] Add `announcement_enabled` toggle to guild config schema
- [x] Create `announcement_channel_id` storage in guild config
- [x] Add `announcement_mention_type` setting (none, everyone, here, role)
- [x] Implement `announcement_role_id` for custom role mentions
- [x] **LINT CHECK**: Run `docker-compose run lint` to verify code quality

### Template Management
- [x] Create nested `announcement_templates` structure in config
- [x] Add method to store custom templates by holiday and phase
- [x] Implement template retrieval with fallback to defaults
- [x] Add validation for user-provided templates
- [x] Create helper method to list available templates
- [x] **LINT CHECK**: Run `docker-compose run lint` to verify code quality

### Announcement Tracking
- [x] Add `last_announcement` tracking for each holiday phase
- [x] Create method to update last announcement timestamp
- [x] Implement method to check if announcement is due for a phase
- [x] Add helper to clear announcement history
- [x] **LINT CHECK**: Run `docker-compose run lint` to verify code quality

### Configuration Integration
- [x] Modify `HolidayAnnouncer` to use config for channel selection
- [x] Update announcement methods to respect enabled/disabled setting
- [x] Integrate mention settings with announcement methods
- [x] Implement custom template application in get_holiday_message()
- [x] Implement config migration for existing installations
- [x] **LINT CHECK**: Run `docker-compose run lint` to verify code quality

### Configuration Accessor Methods
- [x] Create get_announcement_config() method
- [x] Implement set_announcement_enabled() method
- [x] Add set_announcement_channel() method
- [x] Create set_mention_settings() method
- [x] Implement get/set methods for templates
- [x] **LINT CHECK**: Run `docker-compose run lint` to verify code quality

## Integration with Holiday Logic

- [x] Use `DateUtil.add_days()` and `subtract_days()` for holiday timing calculations
- [x] Integrate `DateUtil.str_to_date()` for parsing holiday dates
- [x] Leverage `DateUtil` for phase detection (before, during, after)
- [x] **LINT CHECK**: Run `docker-compose run lint` to verify code quality
- [x] Implement `_is_announcement_needed()` using existing date comparison methods
- [x] Add `_handle_holiday_announcement()` method to `SeasonalRoles` cog
- [x] Connect holiday timing detection to appropriate announcement methods
- [x] Use `DateUtil.get_presentable_date()` for human-readable dates in announcements
- [x] **LINT CHECK**: Run `docker-compose run lint` to verify code quality
- [x] Add announcement tracking to prevent duplicate announcements
- [x] Utilize `DateUtil` for proper date comparisons across year transitions
- [x] Add conditional announcement logic based on configuration settings

## Standalone Announce Cog

- [x] Create basic cog structure
  - [x] Create `__init__.py` with proper imports and setup function
  - [x] Create `info.json` with proper metadata
  - [x] Create `announce_cog.py` with basic class structure
- [x] Implement configuration system
  - [x] Set up config defaults for channels, templates, etc.
  - [x] Add permission system for controlling access
  - [x] Add utility methods for checking permissions
- [x] Channel management
  - [x] Add commands to add/remove channels
  - [x] Add commands to set default channel
  - [x] Add command to list configured channels
- [x] Basic announcement commands
  - [x] Add text announcement command
  - [x] Add embed announcement command
  - [x] Add templated announcement command
  - [x] Add history tracking
- [x] Template system
  - [x] Add template management commands
  - [x] Implement template storage mechanism
  - [x] Add template preview functionality
  - [x] Add template use command
- [x] Scheduled announcements
  - [x] Add background task for checking schedules
  - [x] Add commands to schedule one-time announcements
  - [x] Add commands to schedule recurring announcements
  - [x] Add commands to list and cancel scheduled announcements
- [x] History management
  - [x] Add commands to view announcement history
  - [x] Add limit to history length to prevent DB bloat
  - [x] Add command to clear history

## Command Interface for SeasonalRoles

- [x] Create `/seasonal announce channel` command
- [x] Implement `/seasonal announce preview` command
- [x] **LINT CHECK**: Run `docker-compose run lint` to verify code quality
- [x] Add `/seasonal announce toggle` command
- [x] Create `/seasonal announce template` command for customization
- [x] Implement command to list current announcement settings

## Content Creation

- [ ] Write default "before" templates for all pre-configured holidays
- [ ] Write default "during" templates for all pre-configured holidays
- [ ] Write default "after" templates for all pre-configured holidays
- [ ] Create visual embeds that match holiday themes
- [ ] Add holiday-specific imagery recommendations

## Code Quality & Maintenance

- [x] **LINT CHECK**: Run full linting after initial utilities creation
- [x] **LINT CHECK**: Run full linting after holiday announcer implementation
- [x] **LINT CHECK**: Run full linting after integration with holiday logic
- [ ] **LINT CHECK**: Run full linting after standalone cog implementation
- [ ] Create pre-commit Git hook to automatically run linting
- [ ] Set up type checking with mypy for critical modules
- [ ] Verify PEP 8 compliance across all new code
- [ ] Run security checking tools on announcement code
- [ ] Ensure proper docstrings for all public functions and classes
- [ ] Verify import organization and optimize imports

## Testing and Quality Assurance

- [ ] Create unit tests for announcement utilities
- [ ] Implement dry-run mode for announcements
- [ ] Test announcements in a development server
- [ ] **LINT CHECK**: Run `docker-compose run lint` before integration testing
- [ ] Verify proper timing of announcement triggers
- [ ] Test customization and persistence of settings
- [ ] Test standalone Announce cog functionality
- [ ] Verify proper separation between SeasonalRoles and Announce cog
- [ ] **LINT CHECK**: Run final linting before release

## Documentation

- [x] Update the README.md with new features
- [x] Create comprehensive documentation for the Announce cog
- [ ] Update examples for the SeasonalRoles cog
- [ ] Add diagrams of the workflow
- [ ] Create visual guides for users
