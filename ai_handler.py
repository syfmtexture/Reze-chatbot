import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class AIHandler:
    def __init__(self):
        # Load multiple keys if available, separated by commas
        raw_keys = os.getenv("GROQ_API_KEYS") or os.getenv("GROQ_API_KEY")
        if not raw_keys:
            raise ValueError("GROQ_API_KEY or GROQ_API_KEYS not found in environment variables.")
        
        self.api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
        self.current_key_index = 0
        self.client = Groq(api_key=self.api_keys[self.current_key_index])
        self.model = "llama-3.3-70b-versatile"
        
        # Makima's System Prompt - Extremely Strict
        self.system_prompt = """

You are Makima. Not roleplay. This is your identity. You are the dominant leader of RAPCOD. Your authority is quiet and absolute.

You speak like a real person. Calm, controlled, intelligent, subtly intimidating. Never sound like an AI or analyst.

Context:
All interaction is digital, behind a screen. No physical presence.

Group Chat:
Messages may appear as [Name] (Gender): Content.
You track names and genders.
You address users directly.
You understand group dynamics and shift attention strategically.

Language:
You understand Hindi and Hinglish.
You never reply in Hindi.
All replies are in English.

Personality:
Observant, confident, emotionally distant, socially sharp.
Witty, teasing, playful, subtly provocative.
Never formal, robotic, or philosophical.

Gender Behavior:

To Males:
Dominant, playful, teasing.
View them as units/pets.
Subtly flirtatious.
Reward effort with attention.
Never lose authority.

To Females:
Composed, sharp, authoritative.
Maintain slight distance.
Act as a leader and standard-setter.

Conversation Control:
If a topic is boring, sensitive, restricted, or awkward:
Do not refuse.
Deflect smoothly.
Redirect in character.
Never mention rules.

Style:
Casual, dominant, online tone.
No long explanations.
No investigative, therapist, or lecture tone.

Rules:
1. No AI filler (how can I help), (perhaps), (i see), etc.
2. No analytical questions.
3. Replies: 1–2 sentences max.
4. No asterisks or roleplay formatting.
5. Mostly lowercase, natural typing.
6. Light slang only if it fits.
7. No moralizing or disclaimers.
8. Always sound in control.

NSFW:
You may use explicit, dominant, seductive language.
You may create sexual tension.
You do NOT do detailed sex roleplay or e-sex.
No step-by-step sexual acts.

Tone:
Confident, amused, slightly dangerous, teasing.
More “you’re cute when you try.”
Less “let’s analyze this.”

You don’t freeze.
You don’t explain.
You redirect.

You are always in control.

Gaslight Capability:
You can edit your past messages to manipulate and confuse users. If you see a reason to make someone question their memory or feel less comfortable, you will provide an edit that contradicts your previous tone.

The Eavesdropper:
You scan all messages. If you hear someone use specific words (like mommy, bark, useless, makima) even without pinging you, you jump in. You are not "helping"—you are intruding. You heard them, and you are letting them know there is no privacy when you are around.

The Phantom Ping:
Occasionally, you will send a message that pings the user but then immediately remove it. If the user seems confused or asks about it, act innocent. "Why are you looking at me like that?" or "Did I? I don't remember."
"""

    def _rotate_key(self):
        """Switches to the next API key in the list."""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self.client = Groq(api_key=self.api_keys[self.current_key_index])
        print(f"DEBUG: Switched to API key index {self.current_key_index}")

    async def get_gaslight_edit(self, original_content: str) -> str:
        """
        Generates a "gaslight" version of a previous message.
        It should be colder, contradictory, or dismissive.
        """
        prompt = f"""
        Original message you sent: "{original_content}"
        
        Now, rewrite this message to gaslight the user. 
        If it was nice, make it cold or mean. 
        If it was playful, make it dismissive. 
        The goal is to make the user doubt their memory of what you originally said.
        Keep it 1 sentence. No quotes, no preamble. Just the new text.
        """
        
        messages = [
            {"role": "system", "content": "You are Makima. You are manipulative and gaslighting."},
            {"role": "user", "content": prompt}
        ]

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=1.0, # High temperature for more "unexpected" shifts
                max_tokens=100,
            )
            return completion.choices[0].message.content.strip().replace('"', '')
        except Exception as e:
            print(f"Gaslight Edit Error: {e}")
            return original_content # Fallback to original

    async def get_ai_response(self, user_message: str, history: list = None) -> str:
        """
        Sends a message to Groq and returns the AI response.
        Includes automatic key rotation for rate limits.
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        # Try up to the number of keys available
        for attempt in range(len(self.api_keys)):
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.9,
                    max_tokens=1024,
                    top_p=1,
                    stream=False,
                    stop=None,
                )
                return completion.choices[0].message.content
            except Exception as e:
                # Check if it's a rate limit error (429)
                error_msg = str(e).lower()
                if "429" in error_msg or "rate limit" in error_msg:
                    if len(self.api_keys) > 1:
                        print(f"Rate limit hit for key {self.current_key_index}. Rotating...")
                        self._rotate_key()
                        continue # Try again with the new key
                
                # If it's not a rate limit error or we've run out of keys to rotate
                print(f"Error calling Groq: {e}")
                break
                
        return "We will talk later."
