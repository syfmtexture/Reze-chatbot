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
intents.message_content = True 
intents.members = True          
intents.presences = True        
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
active_users = {} 

# Track persistently gaslit users {user_id: True}
gaslit_users = {}

# Keywords that trigger Reze without a ping
TRIGGER_KEYWORDS = ["reze", "russian", "soviet", "pretty", "cute", "flirt", "heart", "tick-tock", "hehe", "stroll"]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    print("Bot is ready. Mention me or use triggers to start chatting.")
    print("------")

# Track eavesdropping cooldowns {channel_id: datetime}
eavesdropping_cooldowns = {}

@bot.event
async def on_message(message):
    # Ignore messages from bots (including self and webhooks)
    if message.author.bot:
        return

    # Resolve mentions to @display_names for AI context
    content = message.content
    for mention in message.mentions:
        mention_name = mention.display_name
        content = content.replace(f"<@{mention.id}>", f"@{mention_name}").replace(f"<@!{mention.id}>", f"@{mention_name}")
    clean_content = content.strip()
    
    if not clean_content:
        return

    # Extract author details
    author = message.author
    name = author.display_name
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

    # Identify gender by roles (Update these IDs for your server if needed)
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

    # Persistent Gaslighting: Humiliate every message
    if user_id in gaslit_users:
        async with message.channel.typing():
            # Identify gender
            target_gender = "Unknown"
            if hasattr(author, 'roles'):
                t_role_ids = [role.id for role in author.roles]
                if 916228722678456320 in t_role_ids:
                    target_gender = "Male"
                elif 916228772762619974 in t_role_ids:
                    target_gender = "Female"

            # Generate embarrassing text
            identity_text = await ai.get_identity_theft_text(clean_content, target_gender, name)

            try:
                webhooks = await message.channel.webhooks()
                webhook = discord.utils.get(webhooks, name="Reze System")
                if not webhook:
                    webhook = await message.channel.create_webhook(name="Reze System")

                await message.delete()
                await webhook.send(
                    content=identity_text,
                    username=name,
                    avatar_url=author.display_avatar.url
                )
                return  # Stop processing further for gaslit users
            except Exception as e:
                print(f"Persistent Gaslight Failed: {e}")

    # !gaslight command: Toggle persistent humiliation
    if content_lower.startswith("!gaslight") and message.author.guild_permissions.administrator:
        if not message.mentions:
            await message.reply("mention someone to break their reality.")
            return
            
        target = message.mentions[0]
        if target == bot.user:
            await message.reply("you can't gaslight me.")
            return

        t_id = str(target.id)
        if t_id in gaslit_users:
            del gaslit_users[t_id]
            await message.reply(f"fine. {target.display_name} is no longer hallucinating.")
        else:
            gaslit_users[t_id] = True
            await message.reply(f"{target.display_name} is now under my complete control. every word they say will be... corrected.")
        return

    # !ungaslight command: Admin-only release (alternative to toggle)
    if content_lower.startswith("!ungaslight") and message.author.guild_permissions.administrator:
        if not message.mentions:
            await message.reply("who are you releasing?")
            return
        target = message.mentions[0]
        t_id = str(target.id)
        if t_id in gaslit_users:
            del gaslit_users[t_id]
            await message.reply(f"{target.display_name} can speak for themselves again. for now.")
        else:
            await message.reply("they weren't even under my control. focus.")
        return

    # !judge Command - Psychological Profile
    if clean_content.startswith("!judge"):
        target_user = None
        if message.mentions:
            target_user = message.mentions[0]
        else:
            # Default to author if no mention
            target_user = author

        if target_user == bot.user:
            replies = [
                "judge me? you’re bold. i like that. but maybe you should focus on your own ticking clock first. hehe."
            ]
            await message.reply(random.choice(replies))
            return
        # 1. Gather User Info
        status = str(target_user.status)
        is_mobile = target_user.is_on_mobile()
        join_date = target_user.joined_at.strftime("%Y-%m-%d") if target_user.joined_at else "Unknown"
        
        roles = [r.name for r in target_user.roles if r.name != "@everyone"]
        user_info_str = f"Name: {target_user.display_name}\nStatus: {status}\nPlatform: {'Mobile' if is_mobile else 'Desktop'}\nJoined: {join_date}\nRoles: {', '.join(roles)}"
        
        # 2. Gather Message History (Last 15 from this user in this channel)
        history_text = []
        try:
            async for msg in message.channel.history(limit=50):
                if msg.author == target_user and msg.content:
                    history_text.append(f"{msg.content}")
                if len(history_text) >= 15:
                    break
        except Exception as e:
            print(f"Error fetching history: {e}")
            
        history_str = "\n".join(reversed(history_text))
        
        # 3. Get Avatar URL
        avatar_url = str(target_user.display_avatar.url)
        
        # 4. Generate Profile
        async with message.channel.typing():
            profile = await ai.get_psychological_profile(user_info_str, history_str, avatar_url)
            await message.reply(profile)
        return

    if is_mentioned or has_trigger or is_eavesdropping:
        async with message.channel.typing():
            # If explicit trigger was empty (just a ping), say hello
            if (is_mentioned or has_trigger) and not clean_content:
                await message.reply("what?")
                return

            # Prepare context
            personal_context = f"| Note: {name}'s last few words: {', '.join(user_memory[user_id][-3:])}"
            
            # Special instruction for eavesdropping
            eavesdrop_instruction = ""
            if is_eavesdropping:
                eavesdrop_instruction = "\n[EAVESDROPPING: You were not pinged. Interrupt this conversation with something engaging or sarcastic.]"

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

            # --- MESSAGE SPLITTING LOGIC ---
            # Split by SINGLE newline to create the "multi-text" effect
            chunks = [c.strip() for c in response.split('\n') if c.strip()]
            
            # Fallback: if AI didn't split, but message is huge (>250 chars), split by sentences
            if len(chunks) == 1 and len(chunks[0]) > 250:
                chunks = [c.strip() for c in chunks[0].replace('. ', '.\n').replace('? ', '?\n').split('\n') if c.strip()]

            sent_msg = None
            for i, chunk in enumerate(chunks):
                # Fake typing delay based on chunk length (0.05s per character)
                typing_time = min(len(chunk) * 0.05, 3.0) # Cap at 3 seconds
                
                async with message.channel.typing():
                    await asyncio.sleep(typing_time)
                    
                    if i == 0:
                        # First message is a reply
                        sent_msg = await message.reply(chunk)
                    else:
                        # Subsequent messages are normal channel sends
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
