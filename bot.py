import discord
from discord.ext import commands, tasks
import openai
import logging
import asyncio
import re
from datetime import datetime, timedelta
import os

# ============================
# PERSONALIZATION VARIABLES
# ============================

# Discord Bot Token - set this as an environment variable or paste your token here
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_DISCORD_BOT_TOKEN_HERE")

# OpenAI API Key - set this as an environment variable or paste your key here
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY_HERE")
openai.api_key = OPENAI_API_KEY

# Digest channel name: Change this if you want a different channel name for the digest
DIGEST_CHANNEL_NAME = "digest"

# Channels to exclude (e.g., channels for music recommendations or any others) - Make sure to add the name of your digest channel
EXCLUDE_CHANNELS = ["music-recommendations", "another-channel-to-exclude"]

# ============================
# END OF PERSONALIZATION
# ============================

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Create the bot with message content intent
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Regex pattern to extract URLs from messages
url_pattern = re.compile(r'https?://\S+')

def compress_messages(messages):
    """
    Compresses a list of messages into a single string where each line is formatted as "Username: message".
    """
    compressed_lines = []
    for msg in messages:
        content = msg.content.strip()
        # Exclude empty content or messages from bots
        if content and not msg.author.bot:
            compressed_lines.append(f"{msg.author.display_name}: {content}")
    return "\n".join(compressed_lines)

async def generate_summary(daily_text):
    """
    Uses OpenAI's ChatCompletion to generate a summary of the day's discussion,
    and prepends a title with today's date.
    """
    prompt = (
        "Summarize the following day's discussion on the server in a few succinct paragraphs that focus strictly on the topics and factual points discussed. "
        "Do not add any overall concluding statements, interpretations, or editorial remarks at the end. "
        "Simply describe the conversation without summarizing its overall tone or drawing conclusions.\n\n"
        f"{daily_text}\n\nSummary:"
    )
    system_message = (
        "You are an objective summarizer. Your output should be clear, readable paragraphs that detail the topics and factual content discussed, "
        "without adding any concluding or wrap-up sentences. Do not mention phrases like 'overall' or 'in conclusion' or offer any extra commentary."
    )
    try:
        # Run the blocking OpenAI call in a thread to avoid blocking the async loop
        response = await asyncio.to_thread(
            openai.ChatCompletion.create,
            model="gpt-4o-mini",  # Change the model if needed
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7,
            n=1
        )
        summary = response.choices[0].message.content.strip()
        # Prepend the title with today's date
        title = f"Server Digest for {datetime.utcnow().strftime('%Y-%m-%d')}\n\n"
        return title + summary
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        return "Unable to generate summary for today."

def extract_links(messages, exclude_channel_names=EXCLUDE_CHANNELS):
    """
    Extracts all links found in the messages, excluding those from the specified channels.
    """
    links = set()
    for msg in messages:
        if msg.channel.name in exclude_channel_names:
            continue
        found = url_pattern.findall(msg.content)
        links.update(found)
    return links

async def run_digest_for_guild(guild, from_time, to_time):
    """
    Collects messages within the given time range for a guild, generates a summary,
    compiles shared links, and posts both to the designated digest channel.
    Excludes channels listed in EXCLUDE_CHANNELS.
    """
    all_messages = []
    # Iterate over all text channels in the guild
    for channel in guild.text_channels:
        # Skip excluded channels
        if channel.name in EXCLUDE_CHANNELS:
            logging.info(f"Skipping excluded channel '{channel.name}' in guild '{guild.name}'.")
            continue
        try:
            messages = [msg async for msg in channel.history(limit=None, after=from_time, before=to_time)]
            if messages:
                all_messages.extend(messages)
        except discord.Forbidden:
            logging.info(f"Private channel ignored: '{channel.name}' in guild '{guild.name}'.")
        except Exception as e:
            logging.error(f"Error fetching messages from channel '{channel.name}' in guild '{guild.name}': {e}")

    if not all_messages:
        logging.info(f"No messages found in guild '{guild.name}' between {from_time} and {to_time}.")
        return

    # Create a compressed string of messages for summarization
    daily_text = compress_messages(all_messages)
    logging.info(
        f"In guild '{guild.name}', collected {len(all_messages)} messages. "
        f"Compressed text length is {len(daily_text)} characters."
    )

    # Generate GPT summary
    summary = await generate_summary(daily_text)
    logging.info(f"Generated daily summary for guild '{guild.name}' via GPT.")

    # Extract links excluding those from the specified channels
    links = extract_links(all_messages)
    if links:
        links_text = "\n".join(f"- {link}" for link in sorted(links))
    else:
        links_text = "No links were shared today."

    # Locate the digest channel by name (using the personalized variable)
    digest_channel = discord.utils.get(guild.text_channels, name=DIGEST_CHANNEL_NAME)
    if not digest_channel:
        logging.error(f"No channel named '{DIGEST_CHANNEL_NAME}' found in guild '{guild.name}'.")
        return

    try:
        # Post the summary
        await digest_channel.send("**Daily Summary:**\n" + summary)
        # Post the links message, then suppress embeds for a cleaner look
        links_msg = await digest_channel.send("**Links Shared Today:**\n" + links_text)
        await links_msg.edit(suppress=True)
        logging.info(f"Posted daily digest to '{DIGEST_CHANNEL_NAME}' in guild '{guild.name}'.")
    except Exception as e:
        logging.error(f"Error posting digest in guild '{guild.name}': {e}")

@bot.event
async def on_ready():
    logging.info(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
    daily_digest.start()

@tasks.loop(hours=24)
async def daily_digest():
    """
    Every 24 hours, fetches messages from the past day across each guild,
    generates a GPT summary and compiles a list of shared links, then posts both to the digest channel.
    """
    await bot.wait_until_ready()
    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)
    for guild in bot.guilds:
        await run_digest_for_guild(guild, from_time=yesterday, to_time=now)

@daily_digest.before_loop
async def before_daily_digest():
    """
    Waits until the next midnight (UTC) to start the daily digest.
    """
    now = datetime.utcnow()
    next_run = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    delay = (next_run - now).total_seconds()
    logging.info(f"Daily digest will start in {delay/3600:.2f} hours.")
    await asyncio.sleep(delay)

@bot.command()
async def summarize(ctx):
    """
    Manual command to trigger the summary for the past 24 hours.
    Usage: !summarize
    """
    await bot.wait_until_ready()
    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)
    guild = ctx.guild
    if not guild:
        await ctx.send("This command must be used in a server channel.")
        return
    await ctx.send("Generating a summary of the last 24 hours...")
    await run_digest_for_guild(guild, from_time=yesterday, to_time=now)

if __name__ == "__main__":
    # Attribution: Based on a script by Simon Indelicate.
    bot.run(DISCORD_TOKEN)
