import { useState, useEffect } from 'react';
import Landing from './Landing';
import GameRoom from './GameRoom';
import { socket } from './socket';

function App() {
  const [roomData, setRoomData] = useState(null);

  useEffect(() => {
    socket.connect();

    return () => {
      socket.disconnect();
    };
  }, []);

  const handleJoin = (roomId, playerName) => {
    setRoomData({ roomId, playerName });
  };

  const handleLeave = () => {
    setRoomData(null);
  };

  return (
    <div className="min-h-screen text-cream transition-colors duration-300">
      {!roomData ? (
        <Landing onJoin={handleJoin} />
      ) : (
        <GameRoom
          roomId={roomData.roomId}
          playerName={roomData.playerName}
          onLeave={handleLeave}
        />
      )}
    </div>
  );
}

export default App;
