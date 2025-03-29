# Discord Daily Digest Bot

This bot collects messages from all text channels in a Discord server over the past day, summarizes the discussion using OpenAI's API, and compiles a list of shared links. The summary and links are then posted to a designated digest channel.

## Important Note:

- As written, this bot is not secure. you will need to create a dotenv file for your api keys etc if you want to run it anywhere other than locally.

## Features

- **Daily Digest:** Automatically posts a summary and shared links every 24 hours.
- **Manual Summarization:** Use the `!summarize` command to trigger a digest manually.
- **Customization:** Easily personalize channel names and credentials at the top of the `bot.py` file.
- **Attribution:** This bot is based on a script by Simon Indelicate.

## Setup Instructions

### 1. Create a Discord Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application.
2. Navigate to the "Bot" section and click "Add Bot".
3. Copy the **Bot Token** and save it securely.
4. Under "Privileged Gateway Intents", enable **Message Content Intent**.

### 2. Get an OpenAI API Key

1. Sign up or log in at [OpenAI](https://platform.openai.com/).
2. Navigate to the API section to create a new API key.
3. Copy your **OpenAI API Key**.

### 3. Personalize the Bot

- Open the `bot.py` file.
- Replace the placeholder strings `"YOUR_DISCORD_BOT_TOKEN_HERE"` and `"YOUR_OPENAI_API_KEY_HERE"` with your actual tokens.  
  Alternatively, you can set these as environment variables (`DISCORD_TOKEN` and `OPENAI_API_KEY`).

- Modify `DIGEST_CHANNEL_NAME` if you want the summary to be posted in a channel with a different name.
- Modify `EXCLUDE_CHANNEL_NAME` to ignore link extraction from a specific channel if needed.

### 4. Install Dependencies

Ensure you have Python installed (version 3.8 or higher recommended). Install the required packages using pip:

pip install -r requirements.txt

### 5. Run the Bot Locally or Online

Locally:
Run the bot using:

python bot.py

Online (e.g., Heroku, Replit, etc.):
Make sure you set the required environment variables (DISCORD_TOKEN and OPENAI_API_KEY).
Deploy the code according to your chosen platform's instructions.

### 6. Inviting the Bot to Your Server

Go back to the Discord Developer Portal.
Under "OAuth2" > "URL Generator":
    Select the bot scope.
    Choose the permissions your bot needs (at minimum, it requires permissions to read messages and send messages).
Copy the generated URL and open it in your browser to invite the bot to your server.

### Additional Notes

The bot uses OpenAI's Chat API with a model set as gpt-4o-mini. If you have access to a different model or need to change settings, update the model name and parameters in the generate_summary function.
Logs are output to the console to help monitor the bot’s activity and any potential errors.

Attribution

This bot script is based on work by Simon Indelicate.

Support me if you want [https://ko-fi.com/simonindelicate](https://ko-fi.com/simonindelicate)

Feel free to customize and extend the bot functionality as needed!
