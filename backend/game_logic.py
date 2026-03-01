import spacy
from better_profanity import profanity
import urllib.request
import os
import random
import asyncio
import threading
import re
import numpy as np

# The spaCy model will handle lemmatization.
# IMPORTANT: We lazy-load it to avoid long cold-starts (e.g. on Railway).

VOCAB_URL = "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-no-swears.txt"
VOCAB_FILE = "vocab.txt"

# Keep the model loaded globally so it's not reloaded per room
_nlp = None
_nlp_lock = threading.Lock()


def get_nlp():
    global _nlp
    if _nlp is not None:
        return _nlp

    with _nlp_lock:
        if _nlp is not None:
            return _nlp

        # Default to a smaller model for production (e.g. 1GB Railway instances).
        # Override with SPACY_MODEL=en_core_web_lg if you have enough RAM.
        model_name = os.environ.get("SPACY_MODEL", "en_core_web_md")
        print(f"Loading Spacy model ({model_name})...")
        try:
            # We don't need the full parsing/NER pipeline for gameplay.
            _nlp = spacy.load(model_name, disable=["parser", "ner", "senter"])
        except OSError:
            print(f"Model not found: {model_name}. Run: python -m spacy download {model_name}")
            _nlp = None
        return _nlp

profanity.load_censor_words()

# POS tags that indicate meaningful, tangible words (nouns, verbs, adjectives, adverbs)
MEANINGFUL_POS_TAGS = {"NOUN", "VERB", "ADJ", "ADV", "PROPN"}

# POS tags allowed for RANDOM targets (custom target_word remains unrestricted).
# Intentionally excludes PROPN to avoid city/state/place names as targets.
TARGET_POS_TAGS = {"NOUN", "VERB", "ADJ", "ADV"}

# NER entity types we reject for RANDOM targets. (Single-word NER can be noisy, so
# we keep this list narrow and focused on geographic places.)
DISALLOWED_TARGET_ENTITY_TYPES = {"GPE", "LOC", "FAC"}

# Minimum word length for target words
MIN_WORD_LENGTH = 4

_cache_lock = threading.Lock()
_cached_vocab = None
_cached_meaningful_vocab = None
_cached_vocab_words_with_vectors = None
_cached_vocab_vectors = None
_cached_vocab_vector_norms = None
_cached_vector_dim = None
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

    Restricts targets to TARGET_POS_TAGS while also:
    - respecting MIN_WORD_LENGTH
    - excluding function words
    - avoiding cases like 'days' -> 'day' (too short)
    """
    print("Filtering vocabulary for meaningful random target words...")
    meaningful = []
    for w in vocab[:2000]:
        if not is_valid_random_target_word(w):
            continue
        meaningful.append(w)
    print(f"Found {len(meaningful)} meaningful words from top 2000")
    return meaningful


def ensure_global_vocab_cache():
    global _cached_vocab
    global _cached_meaningful_vocab
    global _cached_vocab_words_with_vectors
    global _cached_vocab_vectors
    global _cached_vocab_vector_norms
    global _cached_vector_dim
    global _cached_family_keys

    nlp = get_nlp()
    if nlp is None:
        raise RuntimeError("Spacy model not loaded.")

    if (
        _cached_vocab is not None
        and _cached_meaningful_vocab is not None
        and _cached_vocab_words_with_vectors is not None
        and _cached_vocab_vectors is not None
        and _cached_vocab_vector_norms is not None
        and _cached_vector_dim is not None
        and _cached_family_keys is not None
    ):
        return

    with _cache_lock:
        if (
            _cached_vocab is not None
            and _cached_meaningful_vocab is not None
            and _cached_vocab_words_with_vectors is not None
            and _cached_vocab_vectors is not None
            and _cached_vocab_vector_norms is not None
            and _cached_vector_dim is not None
            and _cached_family_keys is not None
        ):
            return

        vocab = load_vocab()
        meaningful_vocab = _filter_meaningful_vocab(vocab)

        family_keys = {}
        words_with_vectors = []
        vectors = []

        print("Precomputing family keys and vector cache...")
        for i, (w, doc) in enumerate(zip(vocab, nlp.pipe(vocab, batch_size=512))):
            normalized = (w or "").lower().strip()
            if not normalized:
                continue

            if doc is None or len(doc) == 0:
                family_keys[normalized] = normalized
            else:
                token = doc[0]
                family_keys[normalized] = _word_family_key_from_token(token, normalized)

            lex = nlp.vocab[normalized]
            if lex.has_vector:
                words_with_vectors.append(normalized)
                vectors.append(lex.vector)

            if i > 0 and i % 1000 == 0:
                print(f"  cached {i}/{len(vocab)} words")

        _cached_vocab = vocab
        _cached_meaningful_vocab = meaningful_vocab
        _cached_family_keys = family_keys
        _cached_vocab_words_with_vectors = words_with_vectors
        if vectors:
            mat = np.asarray(vectors, dtype=np.float32)
            _cached_vocab_vectors = mat
            norms = np.linalg.norm(mat, axis=1)
            _cached_vocab_vector_norms = norms.astype(np.float32)
            _cached_vector_dim = int(mat.shape[1])
        else:
            _cached_vocab_vectors = np.zeros((0, 0), dtype=np.float32)
            _cached_vocab_vector_norms = np.zeros((0,), dtype=np.float32)
            _cached_vector_dim = 0


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
    nlp = get_nlp()
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
    nlp = get_nlp()
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


def is_valid_random_target_word(word: str) -> bool:
    """Validate whether a vocab word is eligible for RANDOM target selection.

    Goals:
    - Exclude function words and very short words (via is_meaningful_word + MIN_WORD_LENGTH)
    - Exclude proper nouns (PROPN), especially city/state/place names
    - Keep regular nouns/adjectives/etc. like 'oats', 'kangaroo', 'yellow'

    Note: custom target_word remains unrestricted (handled in ContextoGame.initialize()).
    """
    nlp = get_nlp()
    if nlp is None:
        return False

    w = (word or "").lower().strip()
    if not w:
        return False

    if not is_meaningful_word(w):
        return False

    doc = nlp(w)
    if len(doc) == 0:
        return False

    token = doc[0]

    if token.pos_ not in TARGET_POS_TAGS:
        return False

    # Extra guardrail for geographic-like targets.
    if token.ent_type_ in DISALLOWED_TARGET_ENTITY_TYPES:
        return False

    # If lemma collapses to something too short, skip (e.g. 'days' -> 'day').
    lemma = (token.lemma_ or "").lower().strip()
    if lemma and lemma != w and len(lemma) < MIN_WORD_LENGTH:
        return False

    return True

class ContextoGame:
    def __init__(self):
        self.vocab = None
        self.meaningful_vocab = None
        
        self.vocab_words = []
        self.vocab_vectors = None
        self.vocab_vector_norms = None
        self.vector_dim = 0
        self.target_word = None
        self.target_vector = None
        self.target_vector_norm = None
        self.target_family_key = None
        self.ranks = {}
        self.ranked_vocab = []
        self.family_representatives = {}
    
    def _filter_meaningful_vocab(self):
        """Filter vocabulary for random target selection.

        Restricts targets to TARGET_POS_TAGS while also:
        - respecting MIN_WORD_LENGTH
        - excluding function words
        - avoiding cases like 'days' -> 'day' (too short)
        """
        print("Filtering vocabulary for meaningful random target words...")
        meaningful = []
        for w in self.vocab[:2000]:
            if not is_valid_random_target_word(w):
                continue
            meaningful.append(w)
        print(f"Found {len(meaningful)} meaningful words from top 2000")
        return meaningful

    async def initialize(self, target_word=None, emit_cb=None):
        nlp = get_nlp()
        if nlp is None:
            raise RuntimeError("Spacy model not loaded.")

        if emit_cb:
            await emit_cb("Filtering vectors for vocabulary...")
        print("Filtering vectors for vocabulary...")
        await ensure_global_vocab_cache_async(emit_cb=emit_cb)
        self.vocab = _cached_vocab
        self.meaningful_vocab = _cached_meaningful_vocab
        self.vocab_words = _cached_vocab_words_with_vectors or []
        self.vocab_vectors = _cached_vocab_vectors
        self.vocab_vector_norms = _cached_vocab_vector_norms
        self.vector_dim = int(_cached_vector_dim or 0)
        await asyncio.sleep(0)
                
        if target_word:
            raw_target = target_word.lower().strip()
        else:
            # Select from meaningful words only (no function words like 'the', 'a', 'is')
            raw_target = random.choice(self.meaningful_vocab).lower()
            
        self.target_word = raw_target
        self.target_family_key = get_word_family_key(self.target_word)

        # Prefer a vectorized family key for the target if available.
        target_lookup_word = self.target_word
        lex = nlp.vocab[target_lookup_word]
        if self.target_family_key != self.target_word:
            fam_lex = nlp.vocab[self.target_family_key]
            if fam_lex.has_vector:
                lex = fam_lex
                target_lookup_word = self.target_family_key

        if not lex.has_vector:
            raise ValueError(f"Target word '{self.target_word}' is out of vocabulary.")
        self.target_vector = np.asarray(lex.vector, dtype=np.float32)
        self.target_vector_norm = float(np.linalg.norm(self.target_vector) or 0.0)
        if self.target_vector_norm == 0.0:
            raise ValueError(f"Target word '{self.target_word}' has no usable vector.")
            
        await self._precompute_ranks(emit_cb)

    def load_vocab(self):
        return load_vocab()

    async def _precompute_ranks(self, emit_cb=None):
        if emit_cb:
            await emit_cb("Pre-computing ranks vs target...")
        print(f"Pre-computing ranks vs target: {self.target_word}")
        self.ranked_vocab = []
        self.family_representatives = {}

        family_best = {}
        if self.vocab_vectors is None or self.vocab_vector_norms is None or self.target_vector is None:
            raise RuntimeError("Vectors not initialized.")

        denom = (self.target_vector_norm or 0.0) * self.vocab_vector_norms
        valid = denom > 0
        sims = np.full((len(self.vocab_words),), -1.0, dtype=np.float32)
        if np.any(valid):
            sims[valid] = (self.vocab_vectors[valid] @ self.target_vector) / denom[valid]

        for i, word in enumerate(self.vocab_words):
            family_key = (_cached_family_keys or {}).get(word) or get_word_family_key(word)
            sim = float(sims[i])

            best = family_best.get(family_key)
            if best is None or sim > best[1]:
                family_best[family_key] = (word, sim)

            if i % 1000 == 0:
                await asyncio.sleep(0)

        self.ranked_vocab = sorted(family_best.values(), key=lambda x: x[1], reverse=True)
        self.ranks = {}
        for rank, (word, sim) in enumerate(self.ranked_vocab, start=1):
            family_key = (_cached_family_keys or {}).get(word) or get_word_family_key(word)
            self.ranks[family_key] = rank
            self.family_representatives[family_key] = word

    def process_guess(self, guess):
        raw_guess = guess
        guess = guess.lower().strip()
        
        if len(guess) == 0:
            return {"error": "Empty guess"}

        if not re.fullmatch(r"[a-z]+", guess):
            return {"error": "Letters only (A–Z), single word"}
            
        if profanity.contains_profanity(guess):
            return {"error": "NSFW/Profane word rejected"}
            
        if " " in guess:
            return {"error": "Single words only"}
            
        family_key = get_word_family_key(guess)
        search_word = self.family_representatives.get(family_key, guess)
        nlp = get_nlp()
        if nlp is None:
            return {"error": "Dictionary unavailable (model not loaded)"}

        if self.target_vector is None or not self.target_vector_norm:
            return {"error": "Game not ready"}

        lex = nlp.vocab[search_word]
        if not lex.has_vector:
            lex = nlp.vocab[guess]
            if not lex.has_vector:
                return {"error": "Word not found in dictionary"}

        guess_vec = np.asarray(lex.vector, dtype=np.float32)
        guess_norm = float(np.linalg.norm(guess_vec) or 0.0)
        if guess_norm == 0.0:
            return {"error": "Word vector unavailable"}

        similarity = float((guess_vec @ self.target_vector) / (guess_norm * self.target_vector_norm))
        
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
                family = (_cached_family_keys or {}).get(w) or get_word_family_key(w)
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
            family_key = (_cached_family_keys or {}).get(w) or get_word_family_key(w)

            if family_key == self.target_family_key:
                continue

            # `ranked_vocab` is already unique per family and sorted by similarity.
            # So idx+1 is effectively the rank for that family.
            rank = self.ranks.get(family_key, idx + 1)
            if rank <= target_rank:
                return w
                
        # Fallback if nothing is found
        for w, _ in self.ranked_vocab:
            if ((_cached_family_keys or {}).get(w) or get_word_family_key(w)) != self.target_family_key:
                return w
        return self.ranked_vocab[0][0]
