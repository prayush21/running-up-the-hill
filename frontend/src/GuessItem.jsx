import React, { useEffect, useState } from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

export default function GuessItem({
  guess,
  index,
  isNew,
  isLatest,
  isDuplicateHighlighted,
  playerName,
}) {
  const [showSwoosh, setShowSwoosh] = useState(false);

  useEffect(() => {
    if (isNew) {
      // Small sequential delay based on absolute timing rather than React index if multiple arrive?
      // For simplicity, we just trigger it immediately when it mounts if isNew is true.
      setShowSwoosh(true);
    }
  }, [isNew]);

  // Color mapping based on rank
  const getRankColor = (rank) => {
    if (rank <= 300) return "bg-emerald-500";
    if (rank <= 1500) return "bg-amber-500";
    return "bg-rose-500";
  };

  // Loader width is based on similarity, but scaled a bit since similarities are usually -1 to 1.
  // We clamp it and scale it 0 to 100.
  // We'll normalize 0.1 to 1.0 -> 5% to 100% roughly.
  const widthPercent = Math.max(5, Math.min(100, guess.similarity * 100));

  return (
    <div
      className={cn(
        "relative rounded-xl border overflow-hidden mb-1.5 transition-colors duration-500 bg-blueprint-dark/40",
        isDuplicateHighlighted
          ? "border-amber-400 border-2 shadow-[0_0_20px_rgba(251,191,36,0.8)] scale-[1.02] transition-all duration-300"
          : isLatest
            ? "border-accent border-2 shadow-[0_0_15px_rgba(255,140,0,0.5)]"
            : "border-blueprint-light/50",
        isNew && showSwoosh ? "animate-swoosh" : "",
      )}
    >
      {/* Background Linear Loader component */}
      <div className="absolute inset-0 right-0 pointer-events-none z-0">
        <div
          className={cn(
            "h-full opacity-30 transition-all duration-1000",
            getRankColor(guess.rank),
          )}
          style={{ width: `${widthPercent}%` }}
        />
      </div>

      {/* Content wrapper */}
      <div className="relative z-10 py-1.5 px-3 sm:py-2 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-game text-lg font-bold text-cream tracking-wide">
              {guess.word}
            </span>
            {guess.timesGuessed > 1 && (
              <span className="text-[10px] font-mono tracking-widest uppercase px-2 py-0.5 rounded-full border border-blueprint-light/30 text-cream-dark/70 bg-blueprint-dark/40">
                ×{guess.timesGuessed}
              </span>
            )}
          </div>
          {/* Player name in parenthesis in small letters */}
          <div className="text-[10px] text-cream-dark/60 mt-0 font-mono tracking-wider uppercase">
            ({guess.player_name || "unknown"})
          </div>
        </div>

        <div className="flex flex-col items-end">
          <div className="flex items-baseline space-x-1 sm:space-x-2">
            <span
              className={cn(
                "text-xl font-bold font-mono tracking-widest",
                guess.rank <= 300
                  ? "text-emerald-400"
                  : guess.rank <= 1500
                    ? "text-amber-400"
                    : "text-rose-400",
              )}
            >
              {guess.rank}
            </span>
            <span className="text-[10px] text-cream-dark opacity-50 font-mono">
              / {guess.total_words}
            </span>
          </div>
          <div className="text-[10px] text-cream-dark/60 mt-0 font-mono">
            {guess.similarity > 0 ? (guess.similarity * 100).toFixed(1) : 0}%
          </div>
        </div>
      </div>
    </div>
  );
}
