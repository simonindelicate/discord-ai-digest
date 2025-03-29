# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
- Upcoming features and fixes to be added.

## [1.1.0] - 2025-03-29
### Added
- **Link Previews:** Integrated functionality to fetch link previews using both Newspaper and BeautifulSoup, including fallback support.
- **Reply Context:** Added support for including original message content when a message is a reply (if not already included).
- **Embed Processing:** Extended digest generation to process and include information from message embeds.
- **Admin Command:** Introduced an `!admin` command for manual digest generation with debug logging enabled.
  
### Changed
- **Digest Formatting:** Updated the digest generation logic to group messages by channel and format the output more comprehensively.
- **Summary Generation:** Revised the summarization prompt for OpenAI to focus strictly on topics and factual content grouped by channel.
- **Exclusion List:** Updated the exclusion list to include the digest channel by default to prevent redundant processing.

## [1.0.0] - 2025-03-20
### Added
- **Basic Daily Digest:** Implemented a generic Discord bot that collects messages across channels (excluding specified ones), compresses them, and generates a daily summary using OpenAI's ChatCompletion.
- **Scheduled Digest:** Configured the bot to run a daily digest at midnight (UTC) using `discord.ext.tasks`.
- **Link Extraction:** Added functionality to extract shared links from messages.
- **Manual Command:** Added a manual `!summarize` command to trigger digest generation on demand.
