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
# Track bot's own messages for gaslighting (list of Message objects)
bot_message_history = {}

# Keywords that trigger Makima without a ping
TRIGGER_KEYWORDS = ["mommy", "bark", "chainsaw", "useless", "makima", "control", "dominance", "devil", "contract", "obedient"]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    print("Bot is ready. Mention me or use triggers to start chatting.")
    print("------")

@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Check if the bot is strictly mentioned
    is_mentioned = bot.user in message.mentions
    
    # Check for trigger keywords (case insensitive)
    content_lower = message.content.lower()
    has_trigger = any(word in content_lower for word in TRIGGER_KEYWORDS)

    if is_mentioned or has_trigger:
        async with message.channel.typing():
            # Clean the message (remove all mentions)
            content = message.content
            for mention in message.mentions:
                content = content.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "")
            clean_content = content.strip()
            
            if not clean_content:
                await message.reply("hello.")
                return

            # Extract user info
            author = message.author
            name = author.nick or author.display_name or author.name
            
            # Identify gender by roles
            gender = "Unknown"
            if hasattr(author, 'roles'):
                role_ids = [role.id for role in author.roles]
                if 916228722678456320 in role_ids:
                    gender = "Male"
                elif 916228772762619974 in role_ids:
                    gender = "Female"

            # Get or initialize channel history
            channel_id = str(message.channel.id)
            if channel_id not in channel_memory:
                channel_memory[channel_id] = []
            if channel_id not in bot_message_history:
                bot_message_history[channel_id] = []

            # Format the current message with metadata for the AI's perspective
            formatted_user_message = f"[{name}] ({gender}): {clean_content}"

            # Get AI response
            response = await ai.get_ai_response(formatted_user_message, history=channel_memory[channel_id][-5:])

            # Update memory
            channel_memory[channel_id].append({"role": "user", "content": formatted_user_message})
            channel_memory[channel_id].append({"role": "assistant", "content": response})
            
            # Keep memory lean
            if len(channel_memory[channel_id]) > 10:
                channel_memory[channel_id] = channel_memory[channel_id][-10:]

            # Determine if we should do a Phantom Ping (10% chance)
            is_phantom_ping = random.random() < 0.10
            
            # Send response and store it for gaslighting
            sent_msg = None
            if len(response) > 2000:
                for i in range(0, len(response), 2000):
                    content_to_send = response[i:i+2000]
                    if is_phantom_ping and i == 0:
                        sent_msg = await message.reply(f"<@{message.author.id}> {content_to_send}")
                        await sent_msg.edit(content=content_to_send)
                    else:
                        sent_msg = await message.reply(content_to_send)
            else:
                if is_phantom_ping:
                    sent_msg = await message.reply(f"<@{message.author.id}> {response}")
                    # Immediate edit to remove the ping, creating the "phantom" effect
                    await sent_msg.edit(content=response)
                else:
                    sent_msg = await message.reply(response)

            if sent_msg:
                bot_message_history[channel_id].append(sent_msg)
                if len(bot_message_history[channel_id]) > 5:
                    bot_message_history[channel_id].pop(0)

            # Gaslight Trigger (20% chance for message editing)
            if random.random() < 0.20 and len(bot_message_history[channel_id]) > 1:
                # Pick a random older message (not the one just sent)
                target_msg = random.choice(bot_message_history[channel_id][:-1])
                try:
                    new_gaslight_content = await ai.get_gaslight_edit(target_msg.content)
                    await target_msg.edit(content=new_gaslight_content)
                    print(f"DEBUG: Gaslit message in {channel_id}")
                except Exception as e:
                    print(f"Gaslight Edit Failed: {e}")

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("We will talk later.")
