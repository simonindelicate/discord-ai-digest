import discord
from discord.ext import commands, tasks
import openai
import logging
import asyncio
import re
import requests
from bs4 import BeautifulSoup
from newspaper import Article
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

# Channels to exclude (e.g., channels for music recommendations or any others)
EXCLUDE_CHANNELS = ["music-recommendations", DIGEST_CHANNEL_NAME]

# ============================
# END OF PERSONALIZATION
# ============================

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Bot setup with intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Regex pattern to extract URLs from messages
url_pattern = re.compile(r'https?://\S+')

def split_message(text, limit=2000):
    """Split text into <=2000-char chunks at paragraph boundaries, then raw slices."""
    if len(text) <= limit:
        return [text]
    chunks, buffer = [], ""
    for para in text.split("\n\n"):
        if buffer and len(buffer) + len(para) + 2 <= limit:
            buffer += "\n\n" + para
        else:
            if buffer:
                chunks.append(buffer)
            if len(para) > limit:
                for i in range(0, len(para), limit):
                    chunks.append(para[i:i+limit])
                buffer = ""
            else:
                buffer = para
    if buffer:
        chunks.append(buffer)
    return chunks

def fetch_link_preview(url):
    """
    Attempts to fetch a title for a given URL.
    Uses Newspaper for extraction and falls back to BeautifulSoup if needed.
    For Twitter/X links, simply returns the URL.
    """
    if "x.com" in url or "twitter.com" in url:
        return url, url
    try:
        article = Article(url)
        article.download()
        article.parse()
        return (article.title or url).title(), url
    except Exception:
        try:
            resp = requests.get(url, timeout=5)
            soup = BeautifulSoup(resp.text, 'html.parser')
            title = soup.title.string.strip() if soup.title else url
            return title.title(), url
        except Exception:
            return url, url

async def generate_summary(text):
    """
    Uses OpenAI's ChatCompletion to generate a summary of the day's discussion.
    The prompt instructs the model to focus on topics and factual content grouped by channel.
    """
    prompt = (
        "Summarize the following day's discussion in concise paragraphs focusing strictly on topics and facts. "
        "Group messages by channel. No conclusions or editorial comments.\n\n" + text + "\n\nSummary:"
    )
    system = (
        "You are an objective summarizer. Output clear, factual paragraphs without concluding statements."
    )
    try:
        resp = await asyncio.to_thread(
            openai.ChatCompletion.create,
            model="gpt-4o-mini",  # Change the model if needed
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.7
        )
        summary = resp.choices[0].message.content.strip()

        logging.debug(f"OpenAI summary length: {len(summary)}")
        logging.debug(
            "OpenAI summary preview:\n"
            f"START>>>{summary[:200]}<<<\n"
            f"...END>>>{summary[-200:]}<<<"
        )

        title = f"Server Digest for {datetime.utcnow():%Y-%m-%d}\n\n"
        return title + summary + "\n"
    except Exception as e:
        logging.error(f"Summary error: {e}")
        return "Unable to generate summary today.\n"

async def collect_and_format(guild, from_time, to_time):
    """
    Collects messages from channels (excluding the ones specified) and groups them by channel.
    Formats messages with author, content, and includes context for replies and embeds.
    Also extracts shared links.
    """
    channel_messages = {}
    collected_ids = set()  # Track IDs of messages already included

    for channel in guild.text_channels:
        if channel.name in EXCLUDE_CHANNELS:
            continue
        try:
            msgs = [
                m async for m in channel.history(limit=None, after=from_time, before=to_time)
                if (m.content or m.embeds) and not m.author.bot
            ]
            if msgs:
                channel_messages[channel.name] = msgs
                collected_ids.update(m.id for m in msgs)
        except Exception as e:
            logging.info(f"Skipping {channel.name}: {e}")

    if not channel_messages:
        return None, None

    formatted = []
    for ch, msgs in channel_messages.items():
        formatted.append(f"Channel #{ch}:")
        for m in msgs:
            msg_text = f"{m.author.display_name}: {m.content}"
            # Include original message for replies if not already included
            if m.reference:
                original_msg_id = getattr(m.reference, "message_id", None)
                if original_msg_id and original_msg_id not in collected_ids:
                    original = m.reference.resolved
                    if not original:
                        try:
                            original = await m.channel.fetch_message(original_msg_id)
                        except Exception as e:
                            logging.debug(f"Failed fetching original message: {e}")
                    if original:
                        reply_context = f"[In reply to {original.author.display_name}: {original.content}]"
                        msg_text += f"\n{reply_context}"
            # Process embeds for tweets or other link previews
            if m.embeds:
                for embed in m.embeds:
                    embed_parts = []
                    if embed.title:
                        embed_parts.append(embed.title)
                    if embed.description:
                        embed_parts.append(embed.description)
                    if embed_parts:
                        msg_text += f"\n[Embed: {' - '.join(embed_parts)}]"
            formatted.append(msg_text)
        formatted.append("")

    summary = await generate_summary("\n".join(formatted))

    # Extract and process shared links
    links = sorted({
        link 
        for msgs in channel_messages.values() 
        for m in msgs 
        for link in url_pattern.findall(m.content)
    })
    link_lines = ["**Links Shared Today:**"]
    if links:
        for url in links:
            title, link = await asyncio.to_thread(fetch_link_preview, url)
            link_lines.append(f"**{title}**\n> {link}")
    else:
        link_lines.append("No links were shared today.")

    return summary, "\n".join(link_lines)

async def post_to(channel, summary, links):
    """
    Splits the digest content into chunks if needed and posts the summary and links to the specified channel.
    """
    header = "**Daily Summary:**\n"
    full = header + summary

    # Split and send summary chunks
    summary_chunks = split_message(full)
    logging.debug(f"Summary split into {len(summary_chunks)} chunk(s): {[len(c) for c in summary_chunks]}")
    for i, chunk in enumerate(summary_chunks, 1):
        try:
            await channel.send(chunk, suppress_embeds=True)
            logging.debug(f"Sent summary chunk {i}")
        except Exception as e:
            logging.error(f"Failed sending summary chunk {i}: {e}")

    # Split and send link chunks
    link_chunks = split_message(links)
    logging.debug(f"Links split into {len(link_chunks)} chunk(s): {[len(c) for c in link_chunks]}")
    for i, chunk in enumerate(link_chunks, 1):
        try:
            await channel.send(chunk, suppress_embeds=True)
            logging.debug(f"Sent link chunk {i}")
        except Exception as e:
            logging.error(f"Failed sending link chunk {i}: {e}")

async def run_digest_for_guild(guild, from_time, to_time):
    """
    For a given guild, collects and formats messages, generates a summary,
    and posts both the summary and shared links to the digest channel.
    """
    digest_channel = discord.utils.get(guild.text_channels, name=DIGEST_CHANNEL_NAME)
    if not digest_channel:
        logging.error(f"No channel named '{DIGEST_CHANNEL_NAME}' found in guild '{guild.name}'.")
        return

    summary, links = await collect_and_format(guild, from_time, to_time)
    if summary:
        await post_to(digest_channel, summary, links)
        logging.info(f"Posted digest to '{DIGEST_CHANNEL_NAME}' in guild '{guild.name}'.")

@bot.event
async def on_ready():
    logging.info(f"Bot ready: {bot.user}")
    daily_digest.start()

@tasks.loop(hours=24)
async def daily_digest():
    """
    Every 24 hours, fetch messages from the past day across each guild,
    generate a GPT summary and compile a list of shared links, then post both to the digest channel.
    """
    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)
    for guild in bot.guilds:
        await run_digest_for_guild(guild, yesterday, now)

@daily_digest.before_loop
async def before_daily_digest():
    """
    Waits until the next midnight (UTC) before starting the daily digest loop.
    """
    now = datetime.utcnow()
    target = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    delay = (target - now).total_seconds()
    logging.info(f"Daily digest will start in {delay/3600:.2f} hours.")
    await asyncio.sleep(delay)

@bot.command()
async def summarize(ctx):
    """
    Manual command to trigger digest generation for the past 24 hours.
    Usage: !summarize
    """
    now = datetime.utcnow()
    await run_digest_for_guild(ctx.guild, now - timedelta(days=1), now)

@bot.command()
async def admin(ctx):
    """
    Command to trigger a digest with debug logging enabled.
    Usage: !admin
    """
    now = datetime.utcnow()
    logging.getLogger().setLevel(logging.DEBUG)
    await run_digest_for_guild(ctx.guild, now - timedelta(days=1), now)
    logging.getLogger().setLevel(logging.INFO)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
