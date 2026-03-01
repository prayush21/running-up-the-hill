import spacy
from better_profanity import profanity
import urllib.request
import os
import random
import asyncio
import threading

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

# POS tags that indicate meaningful, tangible words (nouns, verbs, adjectives, adverbs)
MEANINGFUL_POS_TAGS = {"NOUN", "VERB", "ADJ", "ADV", "PROPN"}

# POS tags allowed for RANDOM targets (custom target_word remains unrestricted).
TARGET_POS_TAGS = {"NOUN", "PROPN"}

# Minimum word length for target words
MIN_WORD_LENGTH = 4

_cache_lock = threading.Lock()
_cached_vocab = None
_cached_meaningful_vocab = None
_cached_vocab_docs_with_vectors = None
_cached_doc_by_word = None
_cached_family_keys = None


def _word_family_key_from_token(token, normalized):
    lemma = token.lemma_.lower() if token.lemma_ else normalized

    def normalize_comparative_base(text):
        if text.endswith("ier") and len(text) > 4:
            return text[:-3] + "y"
        if text.endswith("er") and len(text) > 3:
            base = text[:-2]
            if len(base) >= 2 and base[-1] == base[-2]:
                base = base[:-1]
            return base
        return text

    # Group verb inflections (-ed/-ing/-s) to their verb lemma.
    # Guardrail: do not collapse derivational changes like "provider" (NOUN) with "provide" (VERB).
    if token.pos_ == "VERB":
        return lemma

    is_explicit_plural_noun = token.pos_ in {"NOUN", "PROPN"} and "Plur" in token.morph.get("Number")
    is_plural_like_surface = (
        (normalized.endswith("s") or normalized.endswith("es"))
        and normalized != lemma
        and token.tag_ in {"NNS", "NNPS"}
    )
    is_plural_noun = is_explicit_plural_noun or is_plural_like_surface
    is_comparative = token.pos_ in {"ADJ", "ADV"} and "Cmp" in token.morph.get("Degree")

    if is_plural_noun:
        return lemma

    if is_comparative:
        return lemma if lemma != normalized else normalize_comparative_base(normalized)

    return normalized


def load_vocab():
    if not os.path.exists(VOCAB_FILE):
        print("Downloading vocabulary list...")
        import ssl

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(VOCAB_URL, context=ctx) as response, open(VOCAB_FILE, "wb") as out_file:
            out_file.write(response.read())

    with open(VOCAB_FILE, "r") as f:
        return [line.strip().lower() for line in f if line.strip()]


def _filter_meaningful_vocab(vocab):
    """Filter vocabulary for random target selection.

    Restricts targets to NOUN/PROPN while also:
    - respecting MIN_WORD_LENGTH
    - excluding function words
    - avoiding cases like 'days' -> 'day' (too short)
    """
    print("Filtering vocabulary for meaningful NOUN/PROPN target words...")
    meaningful = []
    for w in vocab[:2000]:
        if not is_meaningful_word(w):
            continue
        doc = nlp(w)
        if len(doc) > 0:
            token = doc[0]
            if token.pos_ not in TARGET_POS_TAGS:
                continue
            lemma = token.lemma_
            if lemma != w and len(lemma) < MIN_WORD_LENGTH:
                continue
        meaningful.append(w)
    print(f"Found {len(meaningful)} meaningful words from top 2000")
    return meaningful


def ensure_global_vocab_cache():
    global _cached_vocab
    global _cached_meaningful_vocab
    global _cached_vocab_docs_with_vectors
    global _cached_doc_by_word
    global _cached_family_keys

    if nlp is None:
        raise RuntimeError("Spacy model not loaded.")

    if (
        _cached_vocab is not None
        and _cached_meaningful_vocab is not None
        and _cached_vocab_docs_with_vectors is not None
        and _cached_doc_by_word is not None
        and _cached_family_keys is not None
    ):
        return

    with _cache_lock:
        if (
            _cached_vocab is not None
            and _cached_meaningful_vocab is not None
            and _cached_vocab_docs_with_vectors is not None
            and _cached_doc_by_word is not None
            and _cached_family_keys is not None
        ):
            return

        vocab = load_vocab()
        meaningful_vocab = _filter_meaningful_vocab(vocab)

        vocab_docs_with_vectors = []
        doc_by_word = {}
        family_keys = {}

        print("Precomputing vocab docs (has_vector) and family keys...")
        for w in vocab:
            normalized = w.lower().strip()
            if not normalized:
                continue

            doc = nlp(normalized)
            if len(doc) == 0:
                family_keys[normalized] = normalized
                continue

            token = doc[0]
            family_keys[normalized] = _word_family_key_from_token(token, normalized)

            if doc.has_vector:
                vocab_docs_with_vectors.append(doc)
                doc_by_word[normalized] = doc

        _cached_vocab = vocab
        _cached_meaningful_vocab = meaningful_vocab
        _cached_vocab_docs_with_vectors = vocab_docs_with_vectors
        _cached_doc_by_word = doc_by_word
        _cached_family_keys = family_keys


async def ensure_global_vocab_cache_async(emit_cb=None):
    if emit_cb:
        await emit_cb("Preparing vocabulary cache...")
    await asyncio.to_thread(ensure_global_vocab_cache)


def get_word_family_key(word):
    """Return the strict family key for a word.

    Group only:
    - plural nouns/proper nouns
    - comparative adjectives/adverbs
    - verb inflections (to verb lemma)

    All other forms keep their original lowercase surface form.
    """
    normalized = word.lower().strip()
    if nlp is None or not normalized:
        return normalized

    doc = nlp(normalized)
    if len(doc) == 0:
        return normalized

    token = doc[0]
    return _word_family_key_from_token(token, normalized)

def is_meaningful_word(word):
    """
    Check if a word is meaningful and tangible (not a function word like 'the', 'a', 'is', etc.)
    
    Returns True for nouns, verbs, adjectives, adverbs with length >= MIN_WORD_LENGTH.
    Returns False for:
    - Determiners (the, a, an)
    - Prepositions (in, on, at, above)
    - Pronouns (he, she, it, you, we)
    - Conjunctions (and, but, or)
    - Auxiliary verbs (is, are, was, be, have)
    - Particles (to, not)
    - Words shorter than MIN_WORD_LENGTH
    """
    if nlp is None:
        return False
    
    if len(word) < MIN_WORD_LENGTH:
        return False
    
    doc = nlp(word)
    if len(doc) == 0:
        return False
    
    token = doc[0]
    
    # Check POS tag
    if token.pos_ not in MEANINGFUL_POS_TAGS:
        return False
    
    # Additional check: exclude common auxiliary/function verbs even if tagged as VERB
    function_verbs = {"be", "is", "are", "was", "were", "been", "being", 
                      "have", "has", "had", "having", "do", "does", "did",
                      "will", "would", "shall", "should", "may", "might",
                      "can", "could", "must"}
    if word.lower() in function_verbs:
        return False
    
    return True

class ContextoGame:
    def __init__(self):
        self.vocab = None
        self.meaningful_vocab = None
        
        self.vocab_tokens = []
        self.target_word = None
        self.target_token = None
        self.target_family_key = None
        self.ranks = {}
        self.ranked_vocab = []
        self.family_representatives = {}
        self.family_tokens = {}
    
    def _filter_meaningful_vocab(self):
        """Filter vocabulary for random target selection.

        Restricts targets to NOUN/PROPN while also:
        - respecting MIN_WORD_LENGTH
        - excluding function words
        - avoiding cases like 'days' -> 'day' (too short)
        """
        print("Filtering vocabulary for meaningful NOUN/PROPN target words...")
        meaningful = []
        for w in self.vocab[:2000]:
            if not is_meaningful_word(w):
                continue
            # Also check the lemmatized form
            doc = nlp(w)
            if len(doc) > 0:
                token = doc[0]
                if token.pos_ not in TARGET_POS_TAGS:
                    continue
                lemma = token.lemma_
                # If lemma is different and doesn't meet criteria, skip this word
                if lemma != w and len(lemma) < MIN_WORD_LENGTH:
                    continue
            meaningful.append(w)
        print(f"Found {len(meaningful)} meaningful words from top 2000")
        return meaningful

    async def initialize(self, target_word=None, emit_cb=None):
        if emit_cb:
            await emit_cb("Filtering vectors for vocabulary...")
        print("Filtering vectors for vocabulary...")
        await ensure_global_vocab_cache_async(emit_cb=emit_cb)
        self.vocab = _cached_vocab
        self.meaningful_vocab = _cached_meaningful_vocab
        self.vocab_tokens = _cached_vocab_docs_with_vectors
        await asyncio.sleep(0)
                
        if target_word:
            raw_target = target_word.lower().strip()
        else:
            # Select from meaningful words only (no function words like 'the', 'a', 'is')
            raw_target = random.choice(self.meaningful_vocab).lower()
            
        self.target_word = raw_target
        self.target_family_key = get_word_family_key(self.target_word)

        if self.target_family_key != self.target_word and nlp(self.target_family_key).has_vector:
            target_lookup_word = self.target_family_key
        else:
            target_lookup_word = self.target_word
            
        self.target_token = nlp(target_lookup_word)
        if not self.target_token.has_vector:
            raise ValueError(f"Target word '{self.target_word}' is out of vocabulary.")
            
        await self._precompute_ranks(emit_cb)

    def load_vocab(self):
        return load_vocab()

    async def _precompute_ranks(self, emit_cb=None):
        if emit_cb:
            await emit_cb("Pre-computing ranks vs target...")
        print(f"Pre-computing ranks vs target: {self.target_word}")
        self.ranked_vocab = []
        self.family_representatives = {}
        self.family_tokens = {}

        family_best = {}
        for i, t in enumerate(self.vocab_tokens):
            word = t.text.lower()
            family_key = _cached_family_keys.get(word) if _cached_family_keys is not None else None
            if family_key is None:
                family_key = get_word_family_key(word)
            sim = self.target_token.similarity(t)

            best = family_best.get(family_key)
            if best is None or sim > best[1]:
                family_best[family_key] = (word, sim)

            if i % 1000 == 0:
                await asyncio.sleep(0)

        self.ranked_vocab = sorted(family_best.values(), key=lambda x: x[1], reverse=True)
        self.ranks = {}
        for rank, (word, sim) in enumerate(self.ranked_vocab, start=1):
            family_key = _cached_family_keys.get(word) if _cached_family_keys is not None else None
            if family_key is None:
                family_key = get_word_family_key(word)
            self.ranks[family_key] = rank
            self.family_representatives[family_key] = word
            self.family_tokens[family_key] = (_cached_doc_by_word.get(word) if _cached_doc_by_word is not None else None) or nlp(word)

    def process_guess(self, guess):
        raw_guess = guess
        guess = guess.lower().strip()
        
        if len(guess) == 0:
            return {"error": "Empty guess"}
            
        if profanity.contains_profanity(guess):
            return {"error": "NSFW/Profane word rejected"}
            
        if " " in guess:
            return {"error": "Single words only"}
            
        family_key = get_word_family_key(guess)
        search_word = self.family_representatives.get(family_key, guess)
        guess_token = self.family_tokens.get(family_key, nlp(search_word))
        if not guess_token.has_vector:
            fallback_token = nlp(guess)
            if not fallback_token.has_vector:
                return {"error": "Word not found in dictionary"}
            guess_token = fallback_token
            
        similarity = self.target_token.similarity(guess_token)
        
        rank = self.ranks.get(family_key, None)
        if rank is None:
            # Estimate rank for valid words not in top 10k list
            rank = sum(1 for _, sim in self.ranked_vocab if sim > similarity) + 1
            
        is_correct = (family_key == self.target_family_key)
        
        result = {
            # Display the canonical family form (lemma/singular) even if we used a
            # different representative for similarity/rank lookup.
            "word": family_key,
            "raw_guess": raw_guess,
            "similarity": float(similarity),
            "rank": rank,
            "total_words": len(self.ranked_vocab),
            "is_correct": is_correct
        }

        if is_correct:
            top_words = []
            for w, s in self.ranked_vocab:
                family = get_word_family_key(w)
                if family == self.target_family_key:
                    continue
                top_words.append((family, s))
                if len(top_words) == 10:
                    break
            result["top_10"] = [
                {
                    "word": w,
                    "similarity": float(s),
                    "rank": self.ranks.get(w, r + 2),
                }
                for r, (w, s) in enumerate(top_words)
            ]
            
        return result

    def get_hint_word(self, best_rank=None):
        if best_rank is None or best_rank > 300:
            target_rank = 300
        else:
            target_rank = max(1, best_rank // 2)
            
        # Because guesses are normalized to strict word families, search downward to find
        # a family representative that evaluates to <= target_rank.
        start_idx = min(target_rank - 1, len(self.ranked_vocab) - 1)
        for idx in range(start_idx, -1, -1):
            w = self.ranked_vocab[idx][0]
            family_key = get_word_family_key(w)

            if family_key == self.target_family_key:
                continue
            
            guess_token = self.family_tokens.get(family_key, nlp(w))
            if not guess_token.has_vector:
                continue
                
            similarity = self.target_token.similarity(guess_token)
            rank = self.ranks.get(family_key, None)
            if rank is None:
                rank = sum(1 for _, sim in self.ranked_vocab if sim > similarity) + 1
                
            if rank <= target_rank:
                return w
                
        # Fallback if nothing is found
        for w, _ in self.ranked_vocab:
            if get_word_family_key(w) != self.target_family_key:
                return w
        return self.ranked_vocab[0][0]
