import asyncio
from game_logic import ContextoGame
import sys

async def run_tests():
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

    print("\n✅ All automated tests passed successfully.")

if __name__ == "__main__":
    asyncio.run(run_tests())
