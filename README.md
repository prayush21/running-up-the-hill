# Contexto - Team Edition

A multiplayer word-guessing game inspired by the popular [Contexto](https://contexto.me) game. Players collaborate to find a secret target word by guessing words and receiving feedback based on semantic similarity.

## How to Play

1. **Join or Create a Room**: Enter your name and optionally a room code. Leave the room code blank to create a new game room.

2. **Share the Room**: Share the URL with friends to play together in real-time.

3. **Guess Words**: Submit single-word guesses to find the secret target word. After each guess, you'll see:
   - **Rank**: How close your word is to the target (lower = closer). Rank 1 means you found the target!
   - **Similarity**: A percentage showing semantic closeness to the target word

4. **Collaborate**: All players see everyone's guesses in real-time. Work together to narrow down the target word.

5. **Win**: Find the target word (rank #1) to win the game!

### Tips

- Think about words that are semantically related, not spelled similarly
- Use the hint feature if you're stuck (it will suggest a word closer to the target)
- Words are lemmatized (e.g., "running", "runs" → "run") for consistent matching

## Project Structure

```
running-up-the-hill/
├── backend/                 # Python FastAPI + Socket.IO server
│   ├── main.py              # Server entry point, Socket.IO event handlers
│   ├── game_logic.py        # Core game logic (word similarity, ranking)
│   ├── requirements.txt     # Python dependencies
│   ├── vocab.txt            # Vocabulary list (auto-downloaded)
│   └── test_*.py            # Test files
│
├── frontend/                # React + Vite frontend
│   ├── src/
│   │   ├── App.jsx          # Main app component, routing
│   │   ├── Landing.jsx      # Landing page (join/create room)
│   │   ├── GameRoom.jsx     # Main game interface
│   │   ├── GuessList.jsx    # Displays list of guesses
│   │   ├── GuessItem.jsx    # Individual guess display
│   │   ├── socket.js        # Socket.IO client setup
│   │   ├── main.jsx         # React entry point
│   │   └── *.css            # Styling
│   ├── public/              # Static assets
│   ├── package.json         # Node dependencies
│   ├── vite.config.js       # Vite configuration
│   ├── tailwind.config.js   # Tailwind CSS configuration
│   └── postcss.config.js    # PostCSS configuration
│
└── README.md
```

## Tech Stack

### Backend

- **FastAPI** - Modern Python web framework
- **Socket.IO** - Real-time bidirectional communication
- **spaCy** - NLP library for word embeddings and similarity
- **better-profanity** - Profanity filter

### Frontend

- **React 18** - UI library
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Utility-first CSS framework
- **Socket.IO Client** - Real-time communication with backend

## Getting Started

### Prerequisites

- Python 3.9+
- Node.js 18+
- npm or yarn

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy language model
python -m spacy download en_core_web_lg

# Start the server
python main.py
```

The backend server will start on `http://localhost:8000`.

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will start on `http://localhost:5173`.

## How It Works

1. **Word Similarity**: The game uses spaCy's word vectors (`en_core_web_lg` model) to compute semantic similarity between words.

2. **Ranking**: When the game starts, all words in the vocabulary are pre-ranked by their similarity to the target word. Your guess's rank indicates how many words are more similar to the target.

3. **Target Selection**: Target words are selected from meaningful words only (nouns, verbs, adjectives, adverbs) - avoiding function words like "the", "is", "a".

4. **Multiplayer**: Socket.IO enables real-time synchronization - all players in a room see guesses instantly as they're made.

## License

MIT
