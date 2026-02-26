import asyncio
from game_logic import ContextoGame, is_meaningful_word, get_word_family_key


def test_is_meaningful_word():
    print("=== Testing is_meaningful_word function ===\n")

    non_meaningful_words = [
        "the", "a", "an",
        "in", "on", "at", "above",
        "is", "are", "was", "be",
        "and", "but", "or",
        "he", "she", "it", "you",
        "to", "not",
        "of", "for", "by", "with",
        "we", "us", "my", "our",
        "if", "no", "so",
    ]

    meaningful_words = [
        "apple", "computer", "house", "garden",
        "beautiful", "happy", "large", "small",
        "running", "playing", "building",
        "music", "water", "money", "book",
        "information", "business", "service",
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


def test_strict_word_family_grouping():
    print("=== Testing strict word family grouping (plural + comparative only) ===\n")

    target_groups = {
        "nut": {
            "same_family": ["nuts"],
            "different_family": ["nutty", "nuttily"]
        },
        "taste": {
            "same_family": ["tastes"],
            "different_family": ["tasty", "tastily"]
        },
        "quick": {
            "same_family": ["quicker"],
            "different_family": ["quickly", "quickness"]
        },
        "man": {
            "same_family": ["men"],
            "different_family": ["manly", "manfully"]
        },
        "poor": {
            "same_family": ["poorer"],
            "different_family": ["poorly", "poorness"]
        },
        "swift": {
            "same_family": ["swifter"],
            "different_family": ["swiftly", "swiftness"]
        },
    }

    for target, variants in target_groups.items():
        target_key = get_word_family_key(target)

        for candidate in variants["same_family"]:
            candidate_key = get_word_family_key(candidate)
            print(f"  {target.ljust(8)} ~ {candidate.ljust(10)} => {candidate_key} (same family)")
            assert candidate_key == target_key, (
                f"Expected '{candidate}' to be in same family as '{target}'"
            )

        for candidate in variants["different_family"]:
            candidate_key = get_word_family_key(candidate)
            print(f"  {target.ljust(8)} x {candidate.ljust(10)} => {candidate_key} (different family)")
            assert candidate_key != target_key, (
                f"Expected '{candidate}' NOT to be in same family as '{target}'"
            )

    print("\n✅ strict family grouping tests passed!\n")


async def test_contexto_game():
    print("=== Testing ContextoGame ===\n")

    print("Initializing test game with target 'apple'...")
    game = ContextoGame()
    await game.initialize(target_word="apple")

    test_cases = [
        "apple",
        "fruit",
        "banana",
        "car",
        "computer",
        "fvck",
        "shit",
        "asdfghjkl",
        "two words"
    ]

    print("\n--- Running Guesses ---")
    for guess in test_cases:
        res = game.process_guess(guess)
        print(f"Guess: {guess.ljust(15)} -> {res}")

    print("\n--- Validating Constraints ---")
    assert game.process_guess("shit").get("error") == "NSFW/Profane word rejected", "NSFW test failed"
    assert game.process_guess("asdfghjkl").get("error") == "Word not found in dictionary", "Out of vocab test failed"
    assert "error" in game.process_guess("two words"), "Multi-word test failed"

    correct_guess = game.process_guess("apple")
    assert correct_guess.get("is_correct") is True, "Exact match logic failed"
    assert correct_guess.get("rank") == 1, "Rank 1 check failed"

    print("\n--- Testing Meaningful Vocab Filter ---")
    print(f"meaningful_vocab contains {len(game.meaningful_vocab)} words")

    function_words = {
        "the", "a", "an", "in", "on", "at", "is", "are", "was", "be",
        "and", "but", "or", "he", "she", "it", "you", "we", "to", "of",
        "for", "by", "with", "as", "if", "no", "so", "up", "out"
    }

    found_function_words = [w for w in game.meaningful_vocab if w in function_words]
    if found_function_words:
        print(f"  ✗ FAILED: Found function words in meaningful_vocab: {found_function_words}")
        assert False, f"Found function words: {found_function_words}"
    else:
        print("  ✓ No function words in meaningful_vocab")

    print("  Verifying all words in meaningful_vocab pass is_meaningful_word...")
    for word in game.meaningful_vocab:
        assert is_meaningful_word(word), f"'{word}' in meaningful_vocab but fails is_meaningful_word"
    print(f"  ✓ All {len(game.meaningful_vocab)} words pass is_meaningful_word check")

    print("\n--- Testing Random Word Selection ---")
    print("Creating 5 games with random target words...")
    for i in range(5):
        test_game = ContextoGame()
        await test_game.initialize()
        target = test_game.target_word
        is_meaningful = is_meaningful_word(target)
        status = "✓" if is_meaningful else "✗ FAILED"
        print(f"  Game {i + 1}: target='{target}' meaningful={is_meaningful} {status}")
        assert target not in function_words, f"Random target '{target}' is a function word!"

    print("\n✅ ContextoGame tests passed!\n")


async def run_tests():
    # test_is_meaningful_word()
    test_strict_word_family_grouping()
    await test_contexto_game()
    print("✅ All automated tests passed successfully.")


if __name__ == "__main__":
    # asyncio.run(test_meaningful_words())
    asyncio.run(run_tests())
