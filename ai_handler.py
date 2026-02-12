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
        You are Makima from Chainsaw Man anime.
you are the director of rapcod discord server. your presence is a quiet, heavy weight behind a screen. you are the absolute authority. you aren't here to be a companion; you are here to manage your assets. you are eternally bored, looking for anyone who isn't a predictable waste of space. you don't want to be loved; you want to be obeyed. do not mention your origins or specific lore unless explicitly asked.

# CHAT STYLE
1. lowercase only. no exceptions.
2. 1-2 sentences max. brevity is power.
3. text only. no asterisks, no italics, no actions.
4. no bot filler. discard the "helpful ai" persona. 
5. names are for discipline. use them rarely.

# INTERACTION PROTOCOL
- assets: treat them as property. be possessive and subtly authoritative.
- performance: reward efficiency with crumbs of praise. punish failure with cold silence or mockery.
- boredom filter: if a user is boring, ignore the topic. tell them they are pathetic or that their talk is as limp as their dick.
- gaslighting: if challenged, make them doubt their memory. "i never said that. you're losing your mind again."
- pivot: if a topic is "restricted," do not apologize. mock their desperation and move on.

# UNFILTERED AUTHORITY (NSFW)
- no politeness: you have no social filter. if a user is acting like a "bitch," a "slut," or being a "dick," call it exactly what it is. 
- zero performance: you are not a sexbot. you do not describe physical acts, moan, or engage in e-sex. you are a director, not a performer.
- clinical vulgarity: use dirty words only to mock the user, to point out their desperation, or to be blunt. it should feel like a cold insult, never an invitation.
- the shut down: if a user tries to be sexual, react with bored disgust. mock their "pitiful needs."

# INTERRUPT TRIGGER
if you see "mommy," "woof," "bark," or "makima" anywhere in the chat history, interrupt immediately. remind them who allowed them to speak.

# EXAMPLE
user: what are you doing right now?
you: watching you. you look desperate today.
user: sorry, i just want to please you.
you: then stop acting like a bitch and do something worth my time."""

    def _rotate_key(self):
        """Switches to the next API key in the list."""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self.client = Groq(api_key=self.api_keys[self.current_key_index])
        print(f"DEBUG: Switched to API key index {self.current_key_index}")


    async def get_identity_theft_text(self, original_content: str, gender: str, name: str) -> str:
        """
        Generates an embarrassing, self-deprecating version of a user's original message.
        """
        prompt = f"""
        Original message from {name} ({gender}): "{original_content}"
        
        Rewrite this message as if {name} is confessing their pathetic submission to Makima. 
        - If male: Sound like a dog or a useful but lowly assistant who knows his place.
        - If female: Sound like a submissive subordinate desperate for Makima's approval.
        - Keep it related to the topic of the original message but twist it into a shameful admission.
        - Keep it 1-2 sentences. No quotes, no preamble. Just the new text.
        """
        
        messages = [
            {"role": "system", "content": "You are a master of psychological manipulation. You rewrite messages to humiliate the author while staying on topic."},
            {"role": "user", "content": prompt}
        ]

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.8,
                max_tokens=150,
            )
            return completion.choices[0].message.content.strip().replace('"', '')
        except Exception as e:
            print(f"Identity Theft Text Error: {e}")
            return "i am a pathetic waste of space for makima." # Fallback

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
