import spacy
import time

print("Loading model...")
nlp = spacy.load("en_core_web_lg")
with open("vocab.txt", "r") as f:
    vocab = [line.strip() for line in f if line.strip()]

print("processing", len(vocab), "words")
start = time.time()
vocab_lemmas = set()
for w in vocab:
    doc = nlp(w)
    if len(doc) > 0:
        vocab_lemmas.add(doc[0].lemma_)
print("Done in", time.time() - start)
print("Unique lemmas:", len(vocab_lemmas))
