import os
import random
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from ai_handler import AIHandler
import datetime
import logging
import asyncio
from keep_alive import keep_alive

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True  # Required to read message content
intents.members = True          # Required to see member details
intents.presences = True        # Required to see mobile/desktop status
bot = discord.Client(intents=intents)

# Initialize AI Handler
ai = AIHandler()

# Track last few messages per channel (50 turns = 100 entries)
channel_memory = {}
# Track last 10 messages for each user (individual memory)
user_memory = {}
# Track bot's own messages for gaslighting
bot_message_history = {}
# Track users she has talked to (for Phantom DMs)
active_users = {} # {user_id: {"name": str, "gender": str, "last_seen": datetime}}

# Keywords that trigger Makima without a ping
TRIGGER_KEYWORDS = ["mommy", "bark", "chainsaw", "useless", "makima", "control", "dominance", "devil", "contract", "obedient"]

@tasks.loop(minutes=30)
async def phantom_dm_task():
    """Background task for 3am check-ins."""
    # Note: User requested "no dms", so we skip this if they want zero DM interaction.
    # For now, I'll leave the task running but it won't trigger if active_users is filtered.
    return 

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    print("Bot is ready. Mention me or use triggers to start chatting.")
    print("------")

# Track eavesdropping cooldowns {channel_id: datetime}
eavesdropping_cooldowns = {}

@bot.event
async def on_message(message):
    # Ignore messages from the bot or if not in a guild (No DMs)
    if message.author == bot.user or message.guild is None:
        return

    # Clean the message content for tracking/processing
    content = message.content
    for mention in message.mentions:
        content = content.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "")
    clean_content = content.strip()
    
    if not clean_content:
        return

    # Extract author details
    author = message.author
    name = author.nick or author.display_name or author.name
    user_id = str(author.id)
    channel_id = str(message.channel.id)

    # Initialize memory if needed
    if channel_id not in channel_memory:
        channel_memory[channel_id] = []
    if channel_id not in bot_message_history:
        bot_message_history[channel_id] = []
    if user_id not in user_memory:
        user_memory[user_id] = []

    # Update User Memory (Last 10 messages)
    user_memory[user_id].append(clean_content)
    user_memory[user_id] = user_memory[user_id][-10:]

    # Identify gender by roles
    gender = "Unknown"
    if hasattr(author, 'roles'):
        role_ids = [role.id for role in author.roles]
        if 916228722678456320 in role_ids:
            gender = "Male"
        elif 916228772762619974 in role_ids:
            gender = "Female"

    # Device Stalking
    client_status = "Unknown"
    if hasattr(author, 'status'):
        if author.mobile_status != discord.Status.offline:
            client_status = "Mobile"
        elif author.desktop_status != discord.Status.offline:
            client_status = "Desktop"
        elif author.web_status != discord.Status.offline:
            client_status = "Web"

    # Format the message for context
    formatted_user_message = f"[{name}] ({gender}) [Device: {client_status}]: {clean_content}"

    # Determine triggers
    is_mentioned = bot.user in message.mentions
    content_lower = clean_content.lower()
    has_trigger = any(word in content_lower for word in TRIGGER_KEYWORDS)
    
    # Check for Eavesdropping (5% chance if not triggered, with 1hr cooldown)
    is_eavesdropping = False
    if not (is_mentioned or has_trigger):
        now = datetime.datetime.now()
        # 5% base chance to eavesdrop
        if random.random() < 0.05:
            # Check cooldown
            if channel_id not in eavesdropping_cooldowns or \
               (now - eavesdropping_cooldowns[channel_id]).total_seconds() > 3600:
                is_eavesdropping = True
                eavesdropping_cooldowns[channel_id] = now
                print(f"DEBUG: Eavesdropping on {channel_id}")

    # !gaslight command: Admin-only nuclear option
    if content_lower.startswith("!gaslight") and message.author.guild_permissions.administrator:
        if not message.mentions:
            await message.reply("you need to mention someone to humiliate.")
            return
            
        target = message.mentions[0]
        if target == bot.user:
            await message.reply("you can't gaslight me.")
            return

        # Get target's last message in this channel
        last_msg = None
        async for msg in message.channel.history(limit=50):
            if msg.author == target and msg.id != message.id:
                last_msg = msg
                break
        
        if not last_msg:
            await message.reply("i can't find anything relevant from them.")
            return

        async with message.channel.typing():
            # Identify target gender
            target_gender = "Unknown"
            if hasattr(target, 'roles'):
                t_role_ids = [role.id for role in target.roles]
                if 916228722678456320 in t_role_ids:
                    target_gender = "Male"
                elif 916228772762619974 in t_role_ids:
                    target_gender = "Female"

            # Generate embarrassing text
            t_name = target.nick or target.display_name or target.name
            identity_text = await ai.get_identity_theft_text(last_msg.content, target_gender, t_name)

            # Webhook Logic
            try:
                webhooks = await message.channel.webhooks()
                webhook = discord.utils.get(webhooks, name="Makima System")
                if not webhook:
                    webhook = await message.channel.create_webhook(name="Makima System")

                # Delete original and the command message
                await last_msg.delete()
                await message.delete()

                # Post as user
                await webhook.send(
                    content=identity_text,
                    username=t_name,
                    avatar_url=target.display_avatar.url
                )
                print(f"DEBUG: Identity Theft performed on {t_name}")
            except Exception as e:
                print(f"Webhook/Identity Theft Failed: {e}")
                await message.reply("something went wrong with the reality shift.")
        return

    if is_mentioned or has_trigger or is_eavesdropping:
        async with message.channel.typing():
            # If explicit trigger was empty (just a ping), say hello
            if (is_mentioned or has_trigger) and not clean_content:
                await message.reply("hello.")
                return

            # Prepare context
            personal_context = f"| Note: {name}'s last few words: {', '.join(user_memory[user_id][-3:])}"
            
            # Special instruction for eavesdropping
            eavesdrop_instruction = ""
            if is_eavesdropping:
                eavesdrop_instruction = "\n[EAVESDROPPING: You were not pinged. You are listening to this conversation from the shadows. Interrupt only if it's pathetic, boring, or if you want to silence them. Do not be helpful. Just cut in.]"

            # Get AI response
            response = await ai.get_ai_response(
                formatted_user_message + personal_context + eavesdrop_instruction, 
                history=channel_memory[channel_id][-100:]
            )

            # Update channel memory
            channel_memory[channel_id].append({"role": "user", "content": formatted_user_message})
            channel_memory[channel_id].append({"role": "assistant", "content": response})
            
            # Keep memory lean (50 turns)
            if len(channel_memory[channel_id]) > 100:
                channel_memory[channel_id] = channel_memory[channel_id][-100:]

            # Determine if we should do a Phantom Ping (10% chance)
            is_phantom_ping = random.random() < 0.10
            
            # Split response into chunks for natural delivery
            # Split by double newlines or just use the whole thing if short
            chunks = [c.strip() for c in response.split('\n\n') if c.strip()]
            if not chunks:
                chunks = [response.strip()]

            # Determine if we should do a Phantom Ping (10% chance)
            is_phantom_ping = random.random() < 0.10
            
            sent_msg = None
            for i, chunk in enumerate(chunks):
                if i == 0:
                    # First message is a reply
                    if is_phantom_ping:
                        sent_msg = await message.reply(f"<@{author.id}> {chunk}")
                        await sent_msg.edit(content=chunk)
                    else:
                        sent_msg = await message.reply(chunk)
                else:
                    # Subsequent messages are normal channel sends
                    # Small delay for realism
                    await asyncio.sleep(random.uniform(0.5, 1.2))
                    sent_msg = await message.channel.send(chunk)
                
                # Store sent message for history tracking
                if sent_msg:
                    bot_message_history[channel_id].append(sent_msg)

            # Keep history lean
            if len(bot_message_history[channel_id]) > 5:
                bot_message_history[channel_id] = bot_message_history[channel_id][-5:]


if __name__ == "__main__":
    if TOKEN:
        keep_alive()
        bot.run(TOKEN)
    else:
        print("We will talk later.")
