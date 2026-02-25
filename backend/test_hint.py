import asyncio
from game_logic import ContextoGame

async def main():
    game = ContextoGame()
    await game.initialize('apple')
    print('Initialization done', flush=True)
    
    guesses = ["car", "computer", "orange", "fruit"]
    best_rank = None
    
    for g in guesses:
        res = game.process_guess(g)
        print(f"Guess {g}: {res['rank']}", flush=True)
        if best_rank is None or res['rank'] < best_rank:
            best_rank = res['rank']
            
    print("Best rank is:", best_rank, flush=True)
    
    hint_word = game.get_hint_word(best_rank)
    print("Hint word is:", hint_word, flush=True)
    
    hint_res = game.process_guess(hint_word)
    print("Hint guess result rank:", hint_res['rank'], flush=True)
    
    expected_rank = max(1, best_rank // 2)
    print(f"Expected hint rank: {expected_rank}, Actual hint rank: {hint_res['rank']}", flush=True)
    if expected_rank != hint_res['rank']:
        print("Mismatched hint rank!", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
