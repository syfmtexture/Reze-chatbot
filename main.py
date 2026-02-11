import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from ai_handler import AIHandler

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True  # Required to read message content
bot = discord.Client(intents=intents)

# Initialize AI Handler
ai = AIHandler()

# Simple memory to store last few messages per channel
channel_memory = {}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    print("Bot is ready. Mention me to start chatting.")
    print("------")

@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Check if the bot is strictly mentioned
    is_mentioned = bot.user in message.mentions

    if is_mentioned:
        async with message.channel.typing():
            # Clean the message (remove all mentions)
            content = message.content
            for mention in message.mentions:
                content = content.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "")
            clean_content = content.strip()
            
            if not clean_content:
                await message.reply("hello.")
                return

            # Get or initialize channel history
            channel_id = str(message.channel.id)
            if channel_id not in channel_memory:
                channel_memory[channel_id] = []

            # Get AI response
            response = await ai.get_ai_response(clean_content, history=channel_memory[channel_id][-5:]) # Context of last 5 messages

            # Update memory
            channel_memory[channel_id].append({"role": "user", "content": clean_content})
            channel_memory[channel_id].append({"role": "assistant", "content": response})
            
            # Keep memory lean
            if len(channel_memory[channel_id]) > 10:
                channel_memory[channel_id] = channel_memory[channel_id][-10:]

            # Send response as a single message (handling Discord's 2000-character limit)
            if len(response) > 2000:
                for i in range(0, len(response), 2000):
                    await message.reply(response[i:i+2000])
            else:
                await message.reply(response)

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("We will talk later.")
