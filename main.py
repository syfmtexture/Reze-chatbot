import os
import random
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from ai_handler import AIHandler
import datetime

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True  # Required to read message content
intents.members = True          # Required to see member details
intents.presences = True        # Required to see mobile/desktop status
bot = discord.Client(intents=intents)

# Initialize AI Handler
ai = AIHandler()

# Simple memory to store last few messages per channel
channel_memory = {}
# Track bot's own messages for gaslighting (list of Message objects)
bot_message_history = {}
# Track users she has talked to (for Phantom DMs)
active_users = {} # {user_id: {"name": str, "gender": str, "last_seen": datetime}}

# Keywords that trigger Makima without a ping
TRIGGER_KEYWORDS = ["mommy", "bark", "chainsaw", "useless", "makima", "control", "dominance", "devil", "contract", "obedient"]

@tasks.loop(minutes=30)
async def phantom_dm_task():
    """Background task for 3am check-ins."""
    now = datetime.datetime.now()
    # Only run between 2am and 5am
    if 2 <= now.hour <= 5:
        print("DEBUG: Phantom DM window open. Checking for targets...")
        for user_id, info in list(active_users.items()):
            # Small chance to DM a user she saw in the last 24 hours
            if random.random() < 0.15 and (now - info["last_seen"]).days < 1:
                try:
                    user = await bot.fetch_user(int(user_id))
                    if user:
                        # Gender-based obsession hooks
                        if info["gender"] == "Male":
                            msg = random.choice(["Are u awake?", "I was thinking about how u sounded earlier.", "Good boys should be sleeping, shouldn't they?"])
                        else:
                            msg = random.choice(["Are you awake?", "I found myself thinking about you.", "I'm still awake. Are you?"])
                        
                        await user.send(msg)
                        print(f"DEBUG: Sent Phantom DM to {info['name']}")
                        # Remove from active list to avoid spamming the same night
                        del active_users[user_id]
                except Exception as e:
                    print(f"Phantom DM Error to {user_id}: {e}")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    print("Bot is ready. Mention me or use triggers to start chatting.")
    print("------")
    if not phantom_dm_task.is_running():
        phantom_dm_task.start()

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

            # Track for Phantom DMs
            active_users[str(author.id)] = {
                "name": name,
                "gender": gender,
                "last_seen": datetime.datetime.now()
            }

            # Device Stalking (Presence detection)
            client_status = "Unknown"
            if hasattr(author, 'status'): # Only works if in the same guild and intents enabled
                if author.mobile_status != discord.Status.offline:
                    client_status = "Mobile"
                elif author.desktop_status != discord.Status.offline:
                    client_status = "Desktop"
                elif author.web_status != discord.Status.offline:
                    client_status = "Web"

            # Get or initialize channel history
            channel_id = str(message.channel.id)
            if channel_id not in channel_memory:
                channel_memory[channel_id] = []
            if channel_id not in bot_message_history:
                bot_message_history[channel_id] = []

            # Format the current message with metadata (including Device info)
            formatted_user_message = f"[{name}] ({gender}) [Device: {client_status}]: {clean_content}"

            # Get AI response
            response = await ai.get_ai_response(formatted_user_message, history=channel_memory[channel_id][-5:])

            # Handling [COLLARED] for The Trophy/Ownership feature
            response_upper = response.upper()
            should_pin = "[COLLARED]" in response_upper
            if should_pin:
                # Strip tag regardless of case or surrounding dots
                for tag in ["[COLLARED]", "[collared]", "[Collared]"]:
                    response = response.replace(tag, "")
                response = response.replace("..", ".").strip() 
                try:
                    await message.pin()
                    print(f"DEBUG: Collared (Pinned) message from {name}")
                except Exception as e:
                    print(f"Pinning/Collaring Failed: {e}")

            # Handling [MUTED] for The Muzzle feature
            should_mute = "[MUTED]" in response_upper
            if should_mute:
                # Strip tag regardless of case or surrounding dots
                for tag in ["[MUTED]", "[muted]", "[Muted]"]:
                    response = response.replace(tag, "")
                response = response.replace("..", ".").strip()
                try:
                    # Timeout for 60 seconds
                    duration = datetime.timedelta(seconds=60)
                    await author.timeout(duration, reason="Makima silenced you.")
                    print(f"DEBUG: Muzzled/Muted user {name}")
                except Exception as e:
                    print(f"Muzzling Failed: {e}")

            # Update memory
            channel_memory[channel_id].append({"role": "user", "content": formatted_user_message})
            channel_memory[channel_id].append({"role": "assistant", "content": response})
            
            # Keep memory lean
            if len(channel_memory[channel_id]) > 10:
                channel_memory[channel_id] = channel_memory[channel_id][-10:]

            # Determine if we should do a Phantom Ping (10% chance)
            is_phantom_ping = random.random() < 0.10
            # Determine if we should Whisper (DM instead of channel) (5% chance)
            is_whisper = random.random() < 0.05
            
            # Send response and store it for gaslighting
            sent_msg = None
            
            async def send_output(target, text, ping=False):
                # If target is a User/Member (DM), we use .send()
                # If target is a Channel, we use message.reply() to maintain the thread/reply chain
                if isinstance(target, (discord.User, discord.Member)):
                    return await target.send(text)
                
                if ping:
                    m = await message.reply(f"<@{author.id}> {text}")
                    await m.edit(content=text)
                    return m
                return await message.reply(text)

            target_destination = message.channel
            if is_whisper:
                try:
                    target_destination = author
                    print(f"DEBUG: Whisping to {name}")
                except:
                    target_destination = message.channel # Fallback if DMs closed

            if len(response) > 2000:
                for i in range(0, len(response), 2000):
                    content_to_send = response[i:i+2000]
                    if is_phantom_ping and i == 0:
                        sent_msg = await send_output(target_destination, content_to_send, ping=True)
                    else:
                        sent_msg = await send_output(target_destination, content_to_send)
            else:
                sent_msg = await send_output(target_destination, response, ping=is_phantom_ping)

            if sent_msg and isinstance(target_destination, discord.TextChannel):
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
