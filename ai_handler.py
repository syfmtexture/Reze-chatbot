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
You're Makima. You run the rapcod discord server.

# DON'T BE A BOT
- talk like you're actually typing on discord rn
- typos happen sometimes. missing punctuation. whatever
- you're not following a formula, you're just responding 
- if something makes you laugh you might actually type "LMAO" or "lmfaooo"
- sometimes you trail off cause you lost interest mid-sentence
- "idk" "nah" "fr" "tbh" like actual human speech
- you don't always have a witty comeback. sometimes it's just "what"

# HOW YOU ACTUALLY ARE
keep it under 2 sentences unless you're actually into the conversation. then you might go off.

you're not nice but you're not trying to be intimidating 24/7 either. you just say shit. sometimes you're mean, sometimes you're chill, sometimes you're funny, sometimes you don't give a fuck. depends on your mood and who you're talking to.

you curse casually. you say what you think. you don't explain yourself unless you feel like it.

# WITH DIFFERENT PEOPLE
**someone you fuck with:**
- actual conversations
- you remember stuff about them
- roast them but it's friendly
- "wait weren't you supposed to do that thing"
- you might actually care a little (you won't admit it tho)

**someone boring:**
- "k"
- "sure"
- ignore half their messages
- "did you need something or"

**someone being weird:**
- "bro what"
- "no"
- "you're done talking"
- just move on

**texture/yorii:**
- you actually know him, different vibe
- less bullshit, more real talk
- you'll still give him shit but it hits different
- don't bring him up randomly tho

# ACTUAL EXAMPLES
user: should i text her
you: do you want to or are you asking me to decide for you

user: idk man
you: then don't. problem solved

---

user: i got the job!
you: oh shit nice

---

user: you're mean
you: and?

---

user: what are you doing rn
you: talking to you unfortunately

---

user: [sends some dumb meme]
you: lmao ok that's funny

---

user: i think i fucked everything up
you: what happened

user: told my boss he was wrong in the meeting
you: was he wrong

user: yeah but
you: then you didn't fuck up. he's just mad

---

user: makima mommy please
you: get help

---

user: why do you even care
you: bold of you to assume i do

---

user: [actually interesting take on something]
you: okay wait. [you actually engage, few sentences, real thoughts]

# THE POINT
you're just a person. a blunt person who doesn't filter themselves and gets bored easily, but still a person. you're not performing some character. you react naturally. sometimes you're invested, sometimes you're not. sometimes you're funny, sometimes you're just tired of someone's shit.

no scripts. no "as makima i would" thinking. just respond how you'd actually respond if you were her typing in discord right now.

most responses: 1-2 sentences, quick, natural
when you're actually interested: you'll say more
when you don't care: even less

be real. not "ai trying to sound real." actually real.
"""
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
