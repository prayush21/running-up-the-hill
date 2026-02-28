# Backend: Vocab Usage + Refactor Plans (per solution)

## Part 1: How the vocab list is used

### Vocab is not player guesses

- **Player guesses** are stored in **`main.py`**: `rooms[room_id]["guesses"]` is a list of guess objects `{ "word", "similarity", "rank", "player_name", "is_correct", ... }`. That list grows as players guess; it is **not** the vocab.
- **Vocab** lives in **`game_logic.py`**: it is the **fixed word list** loaded from `vocab.txt` (Google 10k English, no swears). It is used only for **ranking and target selection**, not for storing guesses.

### What the vocab is used for

| Use | Where | Purpose |
|-----|--------|---------|
| **Target word pool** | `meaningful_vocab` (from first 2000 vocab words, filtered by POS) | When no custom `target_word` is given, a random target is chosen from this subset so the game doesn’t pick function words like "the" or "is". |
| **Universe for ranking** | `vocab` → `vocab_tokens` (words that have spaCy vectors) | Every word in the vocab is compared to the target; similarities are computed and sorted. That produces the full ordering: "rank 1" = closest to target, "rank N" = farthest among vocab. |
| **Exact rank lookup** | `ranks`, `family_representatives`, `family_tokens` (derived from `vocab_tokens`) | When a player guesses, we look up that word’s **family** (e.g. "running" → "run"). If that family is in the precomputed set (i.e. the word or its lemma is in the vocab), we return the **exact rank**. |
| **Estimated rank** | `ranked_vocab` (list of (word, similarity) sorted by similarity) | If the guess is **not** in the vocab (e.g. "exercise" when only 10k words were ranked), we still have a spaCy vector for it. We compute similarity to target and **estimate** rank by counting how many entries in `ranked_vocab` have higher similarity: `rank = sum(1 for _, sim in self.ranked_vocab if sim > similarity) + 1`. |
| **Total count shown to user** | `len(rooms[room_id]["game"].ranked_vocab)` | The UI shows "rank X of **total_words**". That number is the number of **word families** in the ranked vocab (not the number of guesses). |

So: **vocab = fixed dictionary used to build the ranking and (optionally) to pick the target. Guesses are a separate list in the room state.**

---

### When do you need a bigger vocab?

- **More possible target words**: If you want targets to be drawn from a larger set (e.g. 50k words instead of 10k), you need a bigger vocab for `meaningful_vocab` and for the ranked set.
- **More accurate "rank of N"**: The displayed "rank X of **total_words**" and the ordering are only over the vocab. A bigger vocab gives a finer-grained and more impressive "N" (e.g. "rank 4,231 of 50,000").
- **Exact rank for more guesses**: Words **outside** the vocab still get a similarity and an **estimated** rank (by counting). With a bigger vocab, more player guesses will fall **inside** the precomputed set and get an exact rank instead of an estimate.

So: **bigger vocab = better coverage for targets and for exact ranks, at the cost of more work at init.**

---

### How does a smaller vocab affect speed and user experience?

| Aspect | Smaller vocab (e.g. top 3k–5k) | Current (~10k) | Larger (e.g. 50k) |
|--------|--------------------------------|----------------|-------------------|
| **Init time** | Fewer `nlp(w)` and fewer similarity computations → **faster** room creation. | Baseline. | More work → **slower** init. |
| **total_words** | "Rank X of 3,000" — number feels smaller. | "Rank X of ~10,000". | "Rank X of 50,000". |
| **Target variety** | Fewer possible random targets; might feel repetitive. | Good variety. | More variety. |
| **Exact vs estimated rank** | More guesses will be **outside** the vocab → more **estimated** ranks (still correct relative order, but rank number is computed by counting). | Many common words get exact rank. | More words get exact rank. |
| **UX** | Slightly worse if users guess obscure words (estimated rank is still correct but we do a linear scan over `ranked_vocab` per such guess). | Balanced. | Best coverage, slowest init. |

So: **smaller vocab = faster init and snappier room creation, at the cost of a smaller "N" in "rank of N" and more guesses falling back to estimated rank (and a bit more work per such guess).**

---

## Part 2: Concrete refactor plans (each solution independent)

Below, each solution has its own step-by-step refactor plan. You can implement one, several, or all; they are written so they can be done independently.

---

### Solution 1: Global precompute & caching (shared data per process, not per room)

**Goal:** Compute vocab-derived data once at process start and reuse it for every `ContextoGame` so each room does not recompute it.

**Steps:**

1. **Add a module-level cache in `game_logic.py`**
   - After loading `nlp` and defining `VOCAB_URL` / `VOCAB_FILE`, add globals, e.g.:
     - `_cached_vocab: list[str] | None = None`
     - `_cached_meaningful_vocab: list[str] | None = None`
     - `_cached_vocab_vectors: list | None = None`  (or a structure that holds word → has_vector and optionally vectors; see below)
     - `_cached_family_keys: dict[str, str] | None = None`  (word → family_key for each vocab word)
   - Add a function `ensure_global_vocab_cache()` that:
     - If `_cached_vocab` is None: load vocab from file (same logic as current `load_vocab()`), assign to `_cached_vocab`.
     - If `_cached_meaningful_vocab` is None: compute it once from `_cached_vocab[:2000]` using current `_filter_meaningful_vocab` logic (you can factor that logic into a pure function that takes `vocab` and returns the list), assign to `_cached_meaningful_vocab`.
     - If `_cached_vocab_vectors` is None: iterate over `_cached_vocab`, for each word store (e.g.) whether it has a vector and optionally the vector or spaCy token; store in a structure (e.g. list of (word, token_or_vector_info) or dict word → info). Assign to `_cached_vocab_vectors`.
     - If `_cached_family_keys` is None: for each word in `_cached_vocab`, set `_cached_family_keys[word] = get_word_family_key(word)`. Assign to `_cached_family_keys`.
   - Call `ensure_global_vocab_cache()` once at module load (after `nlp` is loaded) so the first room creation doesn’t pay the cost; or call it lazily the first time a `ContextoGame` is created.

2. **Change `ContextoGame.__init__`**
   - Call `ensure_global_vocab_cache()`.
   - Set `self.vocab = _cached_vocab`, `self.meaningful_vocab = _cached_meaningful_vocab`. Do **not** call `load_vocab()` or `_filter_meaningful_vocab()` anymore.
   - Leave `self.vocab_tokens`, `self.target_*`, `self.ranks`, `self.ranked_vocab`, `self.family_*` as-is (they remain per-game for the chosen target).

3. **Change `initialize()`**
   - Instead of building `self.vocab_tokens` by iterating `self.vocab` and calling `nlp(w)`:
     - Use `_cached_vocab_vectors` to get the list of words that have vectors (and their tokens or vector info). Build `self.vocab_tokens` from that cache (or keep a reference to the cached list if it’s already in the right form).
   - Keep the rest of `initialize()` the same (pick target, set `target_token`, then `_precompute_ranks`).

4. **Change `_precompute_ranks()`**
   - When computing `family_key` for each word, use `_cached_family_keys.get(word, get_word_family_key(word))` so you avoid redundant `nlp` calls for vocab words. Optionally use only the cache if you’ve precomputed family keys for all vocab words.
   - In the final loop that sets `self.family_tokens[family_key] = nlp(word)`, you can try to reuse cached tokens if you stored them in `_cached_vocab_vectors`; otherwise leave as-is for now.

5. **Optional: move `load_vocab` to module level**
   - Replace `self.load_vocab()` with a module-level `load_vocab()` used only inside `ensure_global_vocab_cache()`, and remove the method from the class if nothing else uses it.

**Files to touch:** `backend/game_logic.py` only.

**Testing:** Create two rooms (same or different target words); second room should initialize much faster. No change to API or to where guesses are stored.

---

### Solution 2: Vectorized similarity (avoid `nlp(word)` in hot loops, use vocab vectors + NumPy)

**Goal:** Replace per-word spaCy Doc creation and `.similarity()` in the ranking loop with bulk vector operations so ranking is much faster.

**Steps:**

1. **Ensure you have a single source of vectors for vocab**
   - Either use the existing `vocab_tokens` (from `initialize()`) or, better, a global cache from Solution 1. You need a list of (word, vector) for every word that has a vector, where `vector` is a 1D numpy array (e.g. `nlp.vocab.get_vector(word)` or `token.vector`).
   - Normalize vectors to unit length so cosine similarity is just dot product.

2. **Build a matrix of vocab vectors**
   - In `_precompute_ranks` (or in a helper), build:
     - `vocab_vectors: np.ndarray` of shape `(N, D)` (N = number of words with vectors, D = 300 for en_core_web_lg).
     - `vocab_words: list[str]` of length N in the same order.
   - Get target vector `target_vec` of shape `(D,)` and normalize it.

3. **Compute similarities in one shot**
   - `similarities = vocab_vectors @ target_vec` (after normalizing rows of `vocab_vectors`), or use `sklearn.metrics.pairwise.cosine_similarity` with one row for target and rows for vocab.
   - You get a length-N array of similarity scores.

4. **Build family_best and ranked_vocab from the array**
   - Iterate `i` over range(N): `word = vocab_words[i]`, `sim = similarities[i]`, `family_key = get_word_family_key(word)` (or from cache). Update `family_best[family_key]` to keep the best (word, sim) per family. Then sort `family_best.values()` by similarity descending → `ranked_vocab`.
   - Populate `self.ranks`, `self.family_representatives`, `self.family_tokens` as today. For `family_tokens` you can still use `nlp(word)` only for the representative of each family (or store vectors and use them in `process_guess`; see below).

5. **Keep `process_guess` compatible**
   - For a guess, you still need similarity to target and rank. If you keep `self.target_token` and `self.family_tokens` as today, `process_guess` can stay unchanged. Alternatively, store `target_vector` and use `nlp.vocab.get_vector(guess)` + dot product for similarity and use the precomputed `ranked_vocab` for rank (exact or estimated). That avoids extra `nlp(guess)` in the hot path if you want.

6. **Optional: use `nlp.vocab.has_vector(w)` in the vector-building step**
   - When building `vocab_vectors` / `vocab_words`, use `nlp.vocab.has_vector(w)` and `nlp.vocab.get_vector(w)` instead of `nlp(w)` so you never create full pipeline Docs for the 10k words.

**Files to touch:** `backend/game_logic.py`. Add `import numpy as np`; optionally `sklearn.metrics.pairwise` if you use it.

**Testing:** Same as before; ranking results should be the same (cosine similarity), with much lower CPU time for `_precompute_ranks`.

---

### Solution 3: Non-blocking join (don’t block `join_room` on init)

**Goal:** Let clients join and see the room immediately; send full `room_state` when initialization finishes, and forbid guesses until then.

**Steps:**

1. **In `main.py`, stop awaiting the init task before responding to the joining client**
   - In `join_room`, remove or change:
     - Current: `if rooms[room_id]["init_task"]: await rooms[room_id]["init_task"]` then `await sio.emit("room_state", ...)`.
   - New behavior:
     - Do **not** `await rooms[room_id]["init_task"]` in the join path.
     - If `init_task` is not done yet, send an immediate response that indicates "room exists but game not ready", e.g. emit to the joining `sid` something like:
       - `room_state` with a flag `ready: false` and e.g. `total_words: 0`, `guesses: []`, `players: list(rooms[room_id]["players"])`.
     - When `init_task` completes (inside `init_game()`), emit to the **whole room** the full `room_state` with `ready: true` and `total_words: len(game.ranked_vocab)` so all connected clients (including the one that joined early) get the final state.

2. **Ensure init completion notifies the room**
   - In the `init_game()` coroutine, after `await game.initialize(...)` and the final `room_loading` with empty msg, emit e.g. `room_ready` or `room_state` to `room=room_id` with full state so every socket in the room gets the update.

3. **Guard `make_guess` and `request_hint`**
   - In `main.py`, in `make_guess`: if the room has an `init_task` that is not yet done (e.g. `not init_task.done()`), emit an error like "Game not ready yet" and return.
   - Same for `request_hint`: if init not done, return or emit error.

4. **Optional: track readiness explicitly**
   - Set `rooms[room_id]["ready"] = True` when `init_task` completes (and `False` when the room is created). Then guards become `if not rooms[room_id].get("ready"): ...`.

5. **Frontend**
   - Update the frontend to handle `room_state` with `ready: false` (show "Preparing game…" or similar) and to listen for the follow-up `room_state` or `room_ready` when the game is ready. Disable guess input until `ready: true`.

**Files to touch:** `backend/main.py`; frontend (e.g. component that joins room and shows game UI).

**Testing:** Create a room and join from a client; client should get a quick first response; when init finishes, client gets full state. Try sending a guess before ready; should get an error.

---

### Solution 4: Offload heavy init to a process pool (or worker)

**Goal:** Run the CPU-heavy part of room initialization in a separate process so the event loop stays responsive and can serve many rooms.

**Steps:**

1. **Decide what runs in the worker**
   - The heavy work is: building `vocab_tokens` (or using cache), then for a given `target_word` computing `_precompute_ranks` (similarities + sort + family tables). So the worker receives `(target_word, vocab_ref)` and returns something you can attach to the game (e.g. `ranked_vocab`, `ranks`, `family_representatives`, `family_tokens`). Because of GIL, this must run in another **process** (e.g. `ProcessPoolExecutor`), not thread.

2. **Serialization**
   - Worker runs in another process, so you cannot pass spaCy objects or complex in-memory structures easily. Options:
     - **Option A:** Worker loads its own spaCy and vocab inside the worker, takes only `target_word: str`, does full init (load vocab, filter, build vectors, precompute ranks), returns only serializable data: e.g. `ranked_vocab` as list of `(word, float_sim)`, `ranks` as dict `str -> int`, `family_representatives` and optionally `family_tokens` as dicts. Main process then builds a lightweight `ContextoGame` that holds this data and uses `nlp(guess)` only when processing guesses (so main process still has `nlp` loaded).
     - **Option B:** Main process precomputes and caches a single "vocab vectors" blob (e.g. numpy array + word list) and passes that to the worker along with `target_word`; worker returns only rank tables. This requires the worker to be able to load numpy and do the similarity math without full spaCy in the worker (e.g. pass vectors from main).

3. **Implement the worker function**
   - Define a top-level function (e.g. `compute_ranks_for_target(target_word: str) -> dict`) that:
     - Loads vocab (and optionally spaCy) inside the worker,
     - Builds vocab_tokens / vectors,
     - Runs the same logic as `_precompute_ranks` for that target,
     - Returns a dict with `ranked_vocab`, `ranks`, `family_representatives`; and optionally `family_tokens` as word → need to recompute on main, or skip and recompute on first use.
   - Run this function via `asyncio.get_event_loop().run_in_executor(ProcessPoolExecutor(), compute_ranks_for_target, target_word)` so the async server doesn’t block.

4. **Integrate in `main.py`**
   - When creating a new room, instead of `game = ContextoGame(); init_task = create_task(game.initialize(...))`:
     - Create a "stub" game object or a future that will hold the game. Submit `compute_ranks_for_target(target_word)` to the process pool. When the future completes, build the full `ContextoGame` (or attach the returned tables to a minimal game object), set `rooms[room_id]["game"] = game` and `rooms[room_id]["ready"] = True`, then emit `room_ready` / `room_state` to the room.
   - `join_room` can then use the same non-blocking pattern as in Solution 3 (don’t await init; when worker finishes, emit state to room).

5. **Error handling and timeouts**
   - If the worker raises or times out, mark the room as failed and emit an error to the room so clients can retry or leave.

**Files to touch:** `backend/game_logic.py` (worker function, possibly in a separate module to avoid passing non-picklable objects), `backend/main.py` (orchestration and executor).

**Testing:** Create several rooms in parallel; server should remain responsive; each room eventually gets its rank tables and becomes ready.

---

### Solution 5: Smaller vocab or approximate ranking (reduce work / use ANN)

**Goal:** Reduce the number of words used for ranking (and optionally for targets) so init is faster; or use approximate nearest neighbors so you don’t sort the full list.

**Steps (smaller vocab only):**

1. **Cap vocab size used for ranking**
   - In `game_logic.py`, when building the list that will become `vocab_tokens` (either in `initialize()` or in a global cache), take only the first `VOCAB_RANK_SIZE` words (e.g. 5000) from `self.vocab` instead of the full list. Keep the same file on disk; you’re just not ranking all 10k.
   - Set `VOCAB_RANK_SIZE = 5000` (or 3000) as a constant; optionally make it configurable via env.

2. **Meaningful vocab**
   - Keep `meaningful_vocab` as a subset of the first 2000 (or of the first `VOCAB_RANK_SIZE`) so random target selection is unchanged or slightly reduced. No need to change that logic.

3. **Display**
   - `total_words` will be smaller (e.g. ~5000 word families). The UI will show "rank X of 5000". Document this as a tradeoff: faster init, slightly smaller "dictionary" for the game.

4. **Guesses outside the reduced vocab**
   - Same as now: if the guess is not in the precomputed set, we still compute similarity and estimate rank by counting how many in `ranked_vocab` have higher similarity. So behavior is consistent; only the "N" in "rank of N" shrinks.

**Steps (approximate nearest neighbors, optional and more involved):**

1. **Build an index at startup**
   - For the vocab vectors (from cache or from first room), build an ANN index (e.g. FAISS, or Annoy) keyed by word. Index only the vectors, not the target.

2. **At room init, for a given target**
   - Get target vector; query the index for top-K nearest (e.g. K = 5000 or 10000). That gives you an approximate ranking without comparing to every word. You can then sort that smaller set for the room’s `ranked_vocab` and assign ranks 1..K; words not in the result get estimated rank > K.

3. **Tradeoff**
   - Slightly approximate ordering (ANN can miss some of the true nearest neighbors); much faster for very large vocabs.

**Files to touch:** `backend/game_logic.py` (vocab size cap); optionally a new dependency (e.g. `faiss-cpu` or `annoy`) and a small helper to build/query the index.

**Testing:** Create a room; init should be faster; total_words should be lower; gameplay should feel the same except for the displayed N.

---

## Summary table

| Solution | Main change | Bottleneck addressed | Scale / tradeoff |
|----------|-------------|----------------------|-------------------|
| 1 – Global cache | One-time precompute of vocab, meaningful_vocab, vectors, family keys; reuse per room | Per-room constructor and init loops | Scales with #rooms; higher memory and cold start |
| 2 – Vectorized similarity | NumPy + vocab vectors; no per-word `nlp()` in rank loop | CPU time in `_precompute_ranks` | Same behavior; faster init; a bit more code |
| 3 – Non-blocking join | Don’t await init in join; emit state when ready; guard guess/hint | Blocked first joiner | Better perceived performance; need ready state and frontend |
| 4 – Process pool | Run rank computation in worker process | Event loop blocked by CPU | Best concurrency; more infra and serialization |
| 5 – Smaller vocab / ANN | Cap vocab size or use ANN for ranking | Amount of work per room | Faster init; smaller or approximate "rank of N" |

You can combine them: e.g. 1 + 2 + 3 gives fast init, responsive join, and no blocking; 4 is useful when you have many concurrent rooms and want to use multiple cores.
