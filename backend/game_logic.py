import spacy
from better_profanity import profanity
import urllib.request
import os
import random
import asyncio

# The spaCy model will handle lemmatization

VOCAB_URL = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt"
VOCAB_FILE = "vocab.txt"

# Keep the model loaded globally so it's not reloaded per room
print("Loading Spacy model (en_core_web_lg)...")
try:
    nlp = spacy.load("en_core_web_lg")
except OSError:
    print("Model not found. Run: python -m spacy download en_core_web_lg")
    nlp = None

profanity.load_censor_words()

class ContextoGame:
    def __init__(self):
        if nlp is None:
            raise RuntimeError("Spacy model not loaded.")
        
        self.vocab = self.load_vocab()
        
        self.vocab_tokens = []
        self.target_word = None
        self.target_token = None
        self.ranks = {}
        self.ranked_vocab = []

    async def initialize(self, target_word=None, emit_cb=None):
        if emit_cb:
            await emit_cb("Filtering vectors for vocabulary...")
        print("Filtering vectors for vocabulary...")
        self.vocab_tokens = []
        for i, w in enumerate(self.vocab):
            t = nlp(w)
            if t.has_vector:
                self.vocab_tokens.append(t)
            if i % 1000 == 0:
                await asyncio.sleep(0)
                
        if target_word:
            raw_target = target_word.lower().strip()
        else:
            raw_target = random.choice(self.vocab[:1000]).lower()
            
        target_doc = nlp(raw_target)
        lemma_target = target_doc[0].lemma_ if len(target_doc) > 0 else raw_target
        self.target_word = lemma_target if nlp(lemma_target).has_vector else raw_target
            
        self.target_token = nlp(self.target_word)
        if not self.target_token.has_vector:
            raise ValueError(f"Target word '{self.target_word}' is out of vocabulary.")
            
        await self._precompute_ranks(emit_cb)

    def load_vocab(self):
        if not os.path.exists(VOCAB_FILE):
            print("Downloading vocabulary list...")
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(VOCAB_URL, context=ctx) as response, open(VOCAB_FILE, 'wb') as out_file:
                out_file.write(response.read())
            
        with open(VOCAB_FILE, "r") as f:
            words = [line.strip().lower() for line in f if line.strip()]
        return words

    async def _precompute_ranks(self, emit_cb=None):
        if emit_cb:
            await emit_cb("Pre-computing ranks vs target...")
        print(f"Pre-computing ranks vs target: {self.target_word}")
        self.ranked_vocab = []
        for i, t in enumerate(self.vocab_tokens):
            sim = self.target_token.similarity(t)
            self.ranked_vocab.append((t.text, sim))
            if i % 1000 == 0:
                await asyncio.sleep(0)
            
        self.ranked_vocab.sort(key=lambda x: x[1], reverse=True)
        self.ranks = {word: rank + 1 for rank, (word, sim) in enumerate(self.ranked_vocab)}

    def process_guess(self, guess):
        guess = guess.lower().strip()
        
        if len(guess) == 0:
            return {"error": "Empty guess"}
            
        if profanity.contains_profanity(guess):
            return {"error": "NSFW/Profane word rejected"}
            
        if " " in guess:
            return {"error": "Single words only"}
            
        # Bring guess to its root form (lemma) if the root is in the vocab
        guess_doc = nlp(guess)
        lemma = guess_doc[0].lemma_ if len(guess_doc) > 0 else guess
        search_word = lemma if nlp(lemma).has_vector else guess

        guess_token = nlp(search_word)
        if not guess_token.has_vector:
            return {"error": "Word not found in dictionary"}
            
        similarity = self.target_token.similarity(guess_token)
        
        rank = self.ranks.get(search_word, None)
        if rank is None:
            # Estimate rank for valid words not in top 10k list
            rank = sum(1 for _, sim in self.ranked_vocab if sim > similarity) + 1
            
        is_correct = (search_word == self.target_word)
        
        result = {
            "word": search_word,
            "similarity": float(similarity),
            "rank": rank,
            "total_words": len(self.ranked_vocab),
            "is_correct": is_correct
        }

        if is_correct:
            result["top_10"] = [{"word": w, "similarity": float(s), "rank": r+2} for r, (w, s) in enumerate(self.ranked_vocab[1:11])]
            
        return result

    def get_hint_word(self, best_rank=None):
        if best_rank is None or best_rank > 300:
            target_rank = 300
        else:
            target_rank = max(1, best_rank // 2)
            
        # Due to stemming in process_guess, the exact word at target_rank might evaluate
        # to a lower rank (like 553 instead of 300) when actually guessed.
        # We search from target_rank downwards to find a word that correctly evaluates to <= target_rank.
        start_idx = min(target_rank - 1, len(self.ranked_vocab) - 1)
        for idx in range(start_idx, -1, -1):
            w = self.ranked_vocab[idx][0]
            
            # Simulate what process_guess does
            guess_doc = nlp(w)
            lemma = guess_doc[0].lemma_ if len(guess_doc) > 0 else w
            search_word = lemma if nlp(lemma).has_vector else w
            
            guess_token = nlp(search_word)
            if not guess_token.has_vector:
                continue
                
            similarity = self.target_token.similarity(guess_token)
            rank = self.ranks.get(search_word, None)
            if rank is None:
                rank = sum(1 for _, sim in self.ranked_vocab if sim > similarity) + 1
                
            if rank <= target_rank:
                return w
                
        # Fallback if nothing is found
        return self.ranked_vocab[0][0]
