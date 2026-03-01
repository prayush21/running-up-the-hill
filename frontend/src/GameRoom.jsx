import React, { useState, useEffect, useRef } from "react";
import { socket } from "./socket";
import GuessList from "./GuessList";

export default function GameRoom({ roomId, playerName, onLeave }) {
  const [guesses, setGuesses] = useState([]);
  const [lastGuess, setLastGuess] = useState(null);
  const [currentGuess, setCurrentGuess] = useState("");
  const [toast, setToast] = useState("");
  const [activeDuplicateWord, setActiveDuplicateWord] = useState(null);
  const [totalWords, setTotalWords] = useState(0);
  const [winningWord, setWinningWord] = useState("");
  const [players, setPlayers] = useState([]);
  const [showPlayers, setShowPlayers] = useState(false);
  const [top10Nearest, setTop10Nearest] = useState(null);
  const [loadingMsg, setLoadingMsg] = useState("Initializing Game...");
  const [isReady, setIsReady] = useState(false);

  const bottomRef = useRef(null);
  const duplicateHighlightTimerRef = useRef(null);

  useEffect(() => {
    socket.emit("join_room", { room_id: roomId, player_name: playerName });

    socket.on("room_loading", (data) => {
      setLoadingMsg(data.msg);
    });

    socket.on("room_state", (state) => {
      const ready = !!state.ready;
      setIsReady(ready);
      if (!ready) {
        // Keep the loading overlay until the server finishes initialization.
        setLoadingMsg((prev) => prev || "Preparing game…");
        return;
      }

      setLoadingMsg("");
      const initialGuesses = (state.guesses || []).map((g) => ({
        ...g,
        isNew: false,
        timesGuessed: 1,
      }));
      setGuesses(initialGuesses);
      setTotalWords(state.total_words || 0);
      if (state.players) setPlayers(state.players);
      setActiveDuplicateWord(null);

      const myGuesses = initialGuesses.filter(
        (g) => g.player_name === playerName,
      );
      if (myGuesses.length > 0) {
        setLastGuess(myGuesses[myGuesses.length - 1]);
      }

      const correct = state.guesses.find((g) => g.is_correct);
      if (correct) {
        setWinningWord(correct.word);
        if (correct.top_10) setTop10Nearest(correct.top_10);
      }
    });

    socket.on("new_guess", (guess) => {
      setGuesses((prev) => {
        const existingIndex = prev.findIndex((g) => g.word === guess.word);
        const newGuesses = [...prev];
        if (existingIndex !== -1) {
          newGuesses[existingIndex] = {
            ...newGuesses[existingIndex],
            timesGuessed: (newGuesses[existingIndex].timesGuessed || 1) + 1,
            duplicateTrigger:
              guess.player_name === playerName
                ? Date.now()
                : newGuesses[existingIndex].duplicateTrigger,
          };
          // Since it's already guessed, only show toast
          if (guess.player_name === playerName) {
            setToast(`Already guessed!`);
            setTimeout(() => setToast(""), 3000);
            setActiveDuplicateWord(guess.word);
            if (duplicateHighlightTimerRef.current) {
              clearTimeout(duplicateHighlightTimerRef.current);
            }
            duplicateHighlightTimerRef.current = setTimeout(() => {
              setActiveDuplicateWord(null);
            }, 2000);
            // Do NOT update Last Guess slot, it's a duplicate
          }
        } else {
          newGuesses.push({ ...guess, isNew: true, timesGuessed: 1 });
          if (guess.player_name === playerName) {
            setLastGuess({ ...guess, isNew: true });
          }
        }
        return newGuesses;
      });

      if (guess.is_correct) {
        setWinningWord(guess.word);
        if (guess.top_10) setTop10Nearest(guess.top_10);
      }

      // Only the player who submitted should auto-scroll to the input.
      // Other players should see a notification without losing their scroll position.
      if (guess.player_name === playerName) {
        setTimeout(() => {
          window.scrollTo({ top: 0, behavior: "smooth" });
        }, 100);
      } else if (guess.player_name) {
        // Only notify if viewer is scrolled down at least one viewport height.
        if (window.scrollY >= window.innerHeight) {
          setToast(`📝 ${guess.player_name} guessed "${guess.word}"`);
          setTimeout(() => setToast(""), 2500);
        }
      }
    });

    socket.on("player_joined", (data) => {
      if (data.player_name !== playerName) {
        setToast(`🎮 ${data.player_name} joined the room`);
        setTimeout(() => setToast(""), 4000); // Changed to exact timeout mapped for slideIn length roughly
      }
      if (data.players) {
        setPlayers(data.players);
      } else {
        setPlayers((prev) =>
          prev.includes(data.player_name) ? prev : [...prev, data.player_name],
        );
      }
    });

    socket.on("player_left", (data) => {
      if (data.players) {
        setPlayers(data.players);
      }
      if (data.player_name) {
        setToast(`👋 ${data.player_name} left the room`);
        setTimeout(() => setToast(""), 4000);
      }
    });

    socket.on("guess_error", (data) => {
      setToast(data.msg);
      setTimeout(() => setToast(""), 3000);
    });

    socket.on("error", (data) => {
      console.error("Socket error:", data);
    });

    return () => {
      socket.off("room_loading");
      socket.off("room_state");
      socket.off("new_guess");
      socket.off("player_joined");
      socket.off("player_left");
      socket.off("guess_error");
      socket.off("error");
      if (duplicateHighlightTimerRef.current) {
        clearTimeout(duplicateHighlightTimerRef.current);
        duplicateHighlightTimerRef.current = null;
      }
    };
  }, [roomId, playerName]);

  const normalizedGuess = currentGuess.toLowerCase().trim();

  const handleGuessSubmit = (e) => {
    e.preventDefault();
    if (!normalizedGuess) return;
    if (!isReady) return;
    if (!/^[a-z]+$/.test(normalizedGuess)) {
      setToast("Not a legal guess. Use letters only (A–Z), single word.");
      setTimeout(() => setToast(""), 3000);
      return;
    }
    socket.emit("make_guess", {
      room_id: roomId,
      player_name: playerName,
      guess: normalizedGuess,
    });
    setCurrentGuess("");
  };

  return (
    <div className="min-h-screen flex flex-col pt-6 pb-6 px-4 relative">
      {loadingMsg && (
        <div className="fixed inset-0 z-[200] bg-blueprint-dark/90 backdrop-blur-md flex items-center justify-center p-4">
          <div className="text-center">
            <div className="w-16 h-16 border-4 border-accent border-t-transparent rounded-full animate-spin mx-auto mb-6 shadow-[0_0_15px_rgba(255,140,0,0.5)]"></div>
            <h2 className="text-2xl font-game font-bold text-cream tracking-widest uppercase mb-2">
              Setting up Game
            </h2>
            <p className="text-emerald-400 font-mono text-sm animate-pulse">
              {loadingMsg}
            </p>
          </div>
        </div>
      )}
      <header className="fixed top-0 inset-x-0 z-50 glass-panel border-x-0 border-t-0 border-b border-blueprint-light p-4 flex items-center justify-between shadow-xl">
        <div className="flex items-center space-x-4">
          <h1 className="text-2xl font-game font-bold text-accent">Contexto</h1>
          <div className="relative">
            <button
              onClick={() => setShowPlayers(!showPlayers)}
              className="px-3 py-1.5 rounded bg-blueprint-dark border border-blueprint-light flex items-center hover:bg-blueprint-light/20 transition-colors shadow-sm"
            >
              <span className="text-xs text-cream-dark opacity-60 mr-2 uppercase tracking-wide hidden sm:inline">
                Room
              </span>
              <span className="font-mono text-accent font-bold tracking-widest">
                {roomId}
              </span>
              <svg
                className={`w-4 h-4 ml-2 text-cream-dark transition-transform ${showPlayers ? "rotate-180" : ""}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M19 9l-7 7-7-7"
                ></path>
              </svg>
            </button>

            {showPlayers && (
              <div className="absolute top-full mt-2 left-0 min-w-[200px] glass-panel border border-blueprint-light rounded-lg shadow-[0_10px_30px_-10px_rgba(26,58,109,0.8)] overflow-hidden z-50 animate-slide-up">
                <div className="px-4 py-2 bg-blueprint-dark/80 border-b border-blueprint-light flex justify-between items-center">
                  <span className="text-xs font-game uppercase text-cream-dark opacity-80">
                    Team Players
                  </span>
                  <span className="text-xs font-mono bg-accent/20 text-accent px-2 py-0.5 rounded-full">
                    {players.length}
                  </span>
                </div>
                <ul className="max-h-48 overflow-y-auto bg-blueprint-dark/40 backdrop-blur-md">
                  {players.map((p, i) => (
                    <li
                      key={i}
                      className="px-4 py-2.5 border-b border-blueprint-light/30 last:border-0 flex items-center space-x-3 hover:bg-blueprint-light/10 transition-colors"
                    >
                      <div className="relative">
                        <div className="w-2.5 h-2.5 rounded-full bg-emerald-400"></div>
                        <div className="absolute inset-0 rounded-full bg-emerald-400 animate-ping opacity-50"></div>
                      </div>
                      <span className="font-mono text-sm text-cream">{p}</span>
                      {p === playerName && (
                        <span className="text-[10px] uppercase text-emerald-400/80 ml-auto border border-emerald-400/30 px-1.5 py-0.5 rounded font-bold">
                          You
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center space-x-4">
          <div className="text-sm font-mono text-cream hidden sm:block">
            Playing as:{" "}
            <span className="text-emerald-400 font-bold">{playerName}</span>
          </div>
          <button
            onClick={() =>
              socket.emit("request_hint", {
                room_id: roomId,
                player_name: playerName,
              })
            }
            disabled={!isReady || !!winningWord}
            className="text-xs uppercase tracking-widest p-2 border border-amber-500/50 text-amber-300 rounded hover:bg-amber-500 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed group relative"
            title="Get a hint"
          >
            <svg
              className="w-5 h-5 group-hover:animate-pulse"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
              />
            </svg>
          </button>
          <button
            onClick={onLeave}
            className="text-xs uppercase tracking-widest px-3 py-2 border border-rose-500/50 text-rose-300 rounded hover:bg-rose-500 hover:text-white transition-colors"
          >
            Leave
          </button>
        </div>
      </header>

      {/* Sticky Input Header */}
      <div className="sticky top-20 z-40 w-full mb-8 mt-24">
        <div className="max-w-xl mx-auto text-center mb-4">
          <div className="inline-flex items-center space-x-2 px-4 py-1.5 rounded-full bg-blueprint-dark/80 border border-blueprint-light backdrop-blur-sm shadow-[0_0_15px_rgba(26,58,109,0.5)]">
            <span className="text-xs uppercase tracking-widest text-cream opacity-70 font-mono">
              Team Guesses
            </span>
            <span className="text-sm font-game font-bold text-accent">
              {guesses.length}
            </span>
          </div>
        </div>
        <div className="max-w-xl mx-auto relative">
          <form onSubmit={handleGuessSubmit} className="relative">
            <input
              type="text"
              value={currentGuess}
              onChange={(e) => setCurrentGuess(e.target.value.toLowerCase())}
              placeholder="Type your guess here..."
              disabled={!isReady || !!winningWord}
              className="w-full bg-blueprint-dark/95 backdrop-blur-sm border-2 border-blueprint-light focus:border-accent rounded-full px-6 py-4 text-lg outline-none text-cream shadow-[0_10px_30px_-10px_rgba(26,58,109,0.8)] transition-all disabled:opacity-50 font-game"
              autoFocus
            />
            <button
              type="submit"
              disabled={!isReady || !normalizedGuess || !!winningWord}
              className="absolute right-2 top-2 bottom-2 bg-accent hover:bg-accent-hover disabled:opacity-50 text-blueprint-dark font-bold px-6 rounded-full transition-all flex items-center justify-center uppercase tracking-widest text-sm"
            >
              Guess
            </button>
          </form>
        </div>
      </div>

      {/* Main Game Area */}
      <main className="flex-1 w-full max-w-2xl mx-auto">
        {guesses.length === 0 ? (
          <div className="text-center mt-12 opacity-60">
            <p className="font-game text-xl mb-2">No guesses yet.</p>
            <p className="text-sm border border-blueprint-light inline-block px-4 py-2 rounded-lg bg-blueprint-dark/50">
              Target word is out of {totalWords} words!
            </p>
          </div>
        ) : (
          <GuessList
            guesses={guesses}
            lastGuess={lastGuess}
            playerName={playerName}
            activeDuplicateWord={activeDuplicateWord}
          />
        )}
      </main>

      {/* Toast Notification */}
      {toast && (
        <div className="fixed top-24 right-4 z-50 bg-emerald-500 text-white px-6 py-3 rounded-lg shadow-2xl font-game font-semibold border border-emerald-400 animate-toast">
          {toast}
        </div>
      )}

      {/* Winning Modal */}
      {winningWord && (
        <div className="fixed inset-0 z-[100] bg-blueprint-dark/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="glass-panel p-8 sm:p-12 rounded-2xl max-w-lg w-full text-center border-accent border-2 animate-pulse-border shadow-[0_0_50px_rgba(255,140,0,0.3)] max-h-[90vh] flex flex-col">
            <h2 className="text-4xl font-game font-bold text-accent mb-2 shrink-0">
              Victory!
            </h2>
            <p className="text-xl text-cream mb-4 shrink-0">
              The word was{" "}
              <span className="font-bold underline italic ml-1 block text-3xl mt-4 text-emerald-400 uppercase tracking-widest">
                {winningWord}
              </span>
            </p>
            <p className="text-cream-dark opacity-80 mb-6 font-mono shrink-0">
              It took your team {guesses.length} guesses.
            </p>

            {top10Nearest && (
              <div className="mb-6 text-left overflow-y-auto pr-2 custom-scrollbar flex-1 min-h-0">
                <h3 className="text-sm tracking-widest uppercase font-game text-accent/80 mb-3 text-center border-b border-blueprint-light pb-2">
                  Top 10 Nearest Words
                </h3>
                <ul className="space-y-2">
                  {top10Nearest.map((w, i) => (
                    <li
                      key={i}
                      className="flex justify-between items-center text-cream font-mono text-sm bg-blueprint-dark/50 px-4 py-2 rounded border border-blueprint-light/30"
                    >
                      <span>
                        <span className="text-emerald-400/70 mr-2">
                          {w.rank}.
                        </span>{" "}
                        {w.word}
                      </span>
                      <span className="text-emerald-400">
                        {(w.similarity * 100).toFixed(2)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <button
              onClick={onLeave}
              className="w-full bg-accent hover:bg-accent-hover text-blueprint-dark font-bold font-game uppercase tracking-widest py-4 px-6 rounded-xl transition-transform active:scale-95 text-xl shrink-0 mt-auto"
            >
              Play Again
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
