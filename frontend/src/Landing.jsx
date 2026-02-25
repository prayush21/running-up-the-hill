import { useState, useEffect } from 'react';

export default function Landing({ onJoin }) {
    const [playerName, setPlayerName] = useState('');
    const [roomCode, setRoomCode] = useState('');

    useEffect(() => {
        // Check URL for room code
        const params = new URLSearchParams(window.location.search);
        const roomParam = params.get('room');
        if (roomParam) {
            setRoomCode(roomParam.toUpperCase());
        }
    }, []);

    const handleJoin = (e) => {
        e.preventDefault();
        if (!playerName.trim()) return;

        // Generate random room if empty
        const finalRoom = roomCode.trim() || Math.random().toString(36).substring(2, 8).toUpperCase();

        // Update URL without refreshing
        const newUrl = `${window.location.pathname}?room=${finalRoom}`;
        window.history.pushState({ path: newUrl }, '', newUrl);

        onJoin(finalRoom, playerName.trim());
    };

    return (
        <div className="flex items-center justify-center min-h-screen p-4">
            <div className="glass-panel p-8 rounded-2xl w-full max-w-md animate-toast">
                <div className="text-center mb-8">
                    <h1 className="text-4xl font-game font-bold tracking-tight text-accent mb-2">Contexto</h1>
                    <p className="text-cream-dark opacity-80 uppercase tracking-widest text-sm">Team Edition</p>
                </div>

                <form onSubmit={handleJoin} className="space-y-6">
                    <div>
                        <label className="block text-sm font-medium mb-2 opacity-80 font-game">Player Name</label>
                        <input
                            type="text"
                            required
                            maxLength={20}
                            value={playerName}
                            onChange={(e) => setPlayerName(e.target.value)}
                            className="w-full bg-blueprint-dark/50 border border-blueprint-light rounded-xl px-4 py-3 text-cream focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-colors font-game"
                            placeholder="Enter your name"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium mb-2 opacity-80 font-game">Room Code (optional)</label>
                        <input
                            type="text"
                            value={roomCode}
                            onChange={(e) => setRoomCode(e.target.value.toUpperCase())}
                            className="w-full bg-blueprint-dark/50 border border-blueprint-light rounded-xl px-4 py-3 text-cream focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-colors uppercase tracking-widest font-mono"
                            placeholder="Leave blank to create new"
                        />
                    </div>

                    <button
                        type="submit"
                        className="w-full bg-accent hover:bg-accent-hover text-blueprint-dark font-game font-bold py-3 px-4 rounded-xl transition-transform active:scale-95 text-lg"
                    >
                        {roomCode ? 'Join Game Night' : 'Start New Game Room'}
                    </button>
                </form>
            </div>
        </div>
    );
}
