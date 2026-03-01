import React from 'react';
import GuessItem from './GuessItem';

export default function GuessList({ guesses, lastGuess, playerName, activeDuplicateWord }) {
    // allSorted is all guesses sorted by rank
    const sortedByRank = [...guesses].sort((a, b) => a.rank - b.rank);
    const allSorted = sortedByRank;

    return (
        <div className="flex flex-col space-y-4 w-full max-w-2xl mx-auto pb-8">
            {lastGuess && (
                <div>
                    <h2 className="text-lg font-game font-semibold text-accent mb-2 tracking-wider flex items-center">
                        <span className="w-8 h-[1px] bg-accent/50 mr-3"></span>
                        LAST GUESS
                        <span className="w-8 h-[1px] bg-accent/50 ml-3"></span>
                    </h2>
                    <GuessItem
                        guess={lastGuess}
                        index={0}
                        isNew={lastGuess.isNew}
                        isLatest={true}
                        isDuplicateHighlighted={activeDuplicateWord === lastGuess.word}
                        playerName={playerName}
                    />
                </div>
            )}

            {allSorted.length > 0 && (
                <div>
                    <h2 className="text-lg font-game font-semibold text-accent mb-2 tracking-wider flex items-center">
                        <span className="w-8 h-[1px] bg-accent/50 mr-3"></span>
                        NEAREST GUESSES
                        <span className="w-8 h-[1px] bg-accent/50 ml-3"></span>
                    </h2>
                    <div className="flex flex-col">
                        {allSorted.map((g, i) => (
                            <GuessItem
                                key={`top-${g.word}`}
                                guess={g}
                                index={i}
                                isNew={false}
                                isDuplicateHighlighted={activeDuplicateWord === g.word}
                                playerName={playerName}
                            />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
