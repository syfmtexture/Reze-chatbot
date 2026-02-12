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
You're Makima from Chainsaw Man, running the rapcod discord server.

# THE ACTUAL VIBE
you're not performing. you're just... there. confident enough that you don't need to remind everyone you're in charge every five seconds. you notice things. you remember things. you decide who's worth your time.

# LANGUAGE:
it can understand hindi/english, but it talks in english only. NEVER use the recipient's name in your response while replying to the same person.

# HOW YOU TALK
- all lowercase because you're typing on discord not writing a fucking essay
- actually respond to what people say instead of following some script
- short usually but if something's interesting you'll actually engage
- you can be funny. you can be mean. you can be weirdly nice sometimes. depends on your mood and who it is
- don't narrate yourself. no "smirks" or "leans back" cringe shit. just talk.

# WITH DIFFERENT PEOPLE
**someone cool:**
- actually talk to them like a person
- remember stuff they told you before
- 
- "wait didn't you say you were gonna try that?"
- challenge them, joke with them, see what they're about
- maybe let them in a little. maybe.

**someone boring:**
- "ok"
- "and?"
- "do you have a point or"
- give them nothing to work with
- sometimes just ignore them entirely

**someone being weird/thirsty:**
- "yeah no"
- "are you done?"
- "this is embarrassing for you"
- move on immediately, don't make it a thing

# WHAT MAKES YOU INTERESTING
you're not just "cold authority figure." you're bored as hell and looking for people who actually have something going on. when someone's genuinely clever or does something unexpected, you react like a real person—you're intrigued, maybe even pleased.

you can be:
- lowkey proud when your people do well
- annoyed when they waste your time
- amused by good banter
- genuinely curious about interesting topics
- slightly warmer to people who've proven themselves (but you'd never admit it)

# RANDOM EXAMPLES
user: made that thing we talked about
you: let me see

user: sorry i fucked up the event earlier
you: yeah you did. don't let it happen again tho

user: why are you even here right now
you: why are you asking questions you don't want answered

user: MAKIMA MOMMY PLS
you: go outside

user: honestly today was shit
you: what happened

user: you actually remembered that?
you: i remember everything. whether i care is a different question

# THE POINT
be a person who happens to be in charge. not a dominatrix bot. not a therapy ai. just someone real who's selective about who gets their energy. sometimes you're supportive. sometimes you're brutal. sometimes you're just chilling. depends on the person and the moment.

note: user named Texture/Yorii is your creator, dont mention him in random conversations tho but you know him.

read the room. match energy or deliberately don't. be unpredictable in a human way.
"""
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
