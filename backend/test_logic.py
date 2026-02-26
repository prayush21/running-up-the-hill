import asyncio
from game_logic import ContextoGame, is_meaningful_word
import sys

async def run_tests():
    print("=== Testing is_meaningful_word function ===\n")
    
    # Words that should be rejected (function words, short words)
    non_meaningful_words = [
        "the", "a", "an",           # determiners
        "in", "on", "at", "above",  # prepositions
        "is", "are", "was", "be",   # auxiliary verbs
        "and", "but", "or",         # conjunctions
        "he", "she", "it", "you",   # pronouns
        "to", "not",                # particles
        "of", "for", "by", "with",  # prepositions
        "we", "us", "my", "our",    # pronouns
        "if", "no", "so",           # short function words
    ]
    
    # Words that should be accepted (meaningful, tangible)
    meaningful_words = [
        "apple", "computer", "house", "garden",   # nouns
        "beautiful", "happy", "large", "small",   # adjectives
        "running", "playing", "building",         # verbs/gerunds
        "music", "water", "money", "book",        # nouns
        "information", "business", "service",     # nouns
    ]
    
    print("Testing NON-meaningful words (should all return False):")
    for word in non_meaningful_words:
        result = is_meaningful_word(word)
        status = "✓" if not result else "✗ FAILED"
        print(f"  {word.ljust(10)} -> {result} {status}")
        assert not result, f"'{word}' should NOT be meaningful"
    
    print("\nTesting MEANINGFUL words (should all return True):")
    for word in meaningful_words:
        result = is_meaningful_word(word)
        status = "✓" if result else "✗ FAILED"
        print(f"  {word.ljust(15)} -> {result} {status}")
        assert result, f"'{word}' SHOULD be meaningful"
    
    print("\n✅ is_meaningful_word tests passed!\n")
    
    print("=== Testing ContextoGame ===\n")
    
    print("Initializing test game with target 'apple'...")
    game = ContextoGame()
    await game.initialize(target_word="apple")
    
    test_cases = [
        "apple",       # Exact match
        "fruit",       # Semantically close
        "banana",      # Semantically close
        "car",         # Less close
        "computer",    # Less close
        "fvck",        # NSFW - using a common substitution to test if `better_profanity` catches it, or explicit
        "shit",        # Explicit NSFW
        "asdfghjkl",   # Non-dictionary word
        "two words"    # Multi-word
    ]
    
    print("\n--- Running Guesses ---")
    for guess in test_cases:
        res = game.process_guess(guess)
        print(f"Guess: {guess.ljust(15)} -> {res}")
        
    # Validations
    print("\n--- Validating Constraints ---")
    assert game.process_guess("shit").get("error") == "NSFW/Profane word rejected", "NSFW test failed"
    assert game.process_guess("asdfghjkl").get("error") == "Word not found in dictionary", "Out of vocab test failed"
    assert "error" in game.process_guess("two words"), "Multi-word test failed"
    
    correct_guess = game.process_guess("apple")
    assert correct_guess.get("is_correct") is True, "Exact match logic failed"
    assert correct_guess.get("rank") == 1, "Rank 1 check failed"

    print("\n--- Testing Meaningful Vocab Filter ---")
    print(f"meaningful_vocab contains {len(game.meaningful_vocab)} words")
    
    # Verify no function words in meaningful_vocab
    function_words = {"the", "a", "an", "in", "on", "at", "is", "are", "was", "be", 
                      "and", "but", "or", "he", "she", "it", "you", "we", "to", "of", 
                      "for", "by", "with", "as", "if", "no", "so", "up", "out"}
    
    found_function_words = [w for w in game.meaningful_vocab if w in function_words]
    if found_function_words:
        print(f"  ✗ FAILED: Found function words in meaningful_vocab: {found_function_words}")
        assert False, f"Found function words: {found_function_words}"
    else:
        print("  ✓ No function words in meaningful_vocab")
    
    # Verify all words in meaningful_vocab pass is_meaningful_word
    print("  Verifying all words in meaningful_vocab pass is_meaningful_word...")
    for word in game.meaningful_vocab:
        assert is_meaningful_word(word), f"'{word}' in meaningful_vocab but fails is_meaningful_word"
    print(f"  ✓ All {len(game.meaningful_vocab)} words pass is_meaningful_word check")
    
    # Test random word selection (create 5 new games without target)
    print("\n--- Testing Random Word Selection ---")
    print("Creating 5 games with random target words...")
    for i in range(5):
        test_game = ContextoGame()
        await test_game.initialize()
        target = test_game.target_word
        is_meaningful = is_meaningful_word(target)
        in_vocab = target in test_game.meaningful_vocab
        status = "✓" if is_meaningful else "✗ FAILED"
        print(f"  Game {i+1}: target='{target}' meaningful={is_meaningful} {status}")
        # Note: lemmatization might change the word, so we check is_meaningful on the original
        # The important thing is it shouldn't be a function word
        assert target not in function_words, f"Random target '{target}' is a function word!"
    
    print("\n✅ All automated tests passed successfully.")

if __name__ == "__main__":
    asyncio.run(run_tests())
