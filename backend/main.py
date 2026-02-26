import uvicorn
import asyncio
from fastapi import FastAPI
import socketio
from game_logic import ContextoGame

# Setup Socket.io and FastAPI
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = FastAPI()
sio_app = socketio.ASGIApp(sio, other_asgi_app=app)

# Store active rooms. Key: room_id, Value: {"game": ContextoGame, "guesses": [], "players": []}
rooms = {}

# Map sid to player info for easy cleanup on disconnect
sid_to_info = {}

@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")
    if sid in sid_to_info:
        info = sid_to_info.pop(sid)
        room_id = info["room_id"]
        player_name = info["player_name"]
        
        if room_id in rooms and player_name in rooms[room_id]["players"]:
            rooms[room_id]["players"].remove(player_name)
            await sio.emit("player_left", {
                "player_name": player_name, 
                "players": list(rooms[room_id]["players"])
            }, room=room_id)

@sio.event
async def join_room(sid, data):
    room_id = data.get("room_id")
    player_name = data.get("player_name")
    target_word = data.get("target_word")  # Optional custom target word
    
    if not room_id or not player_name:
        await sio.emit("error", {"msg": "room_id and player_name required"}, to=sid)
        return
        
    # Initialize room if it doesn't exist
    if room_id not in rooms:
        print(f"Creating new room: {room_id}" + (f" with target word: {target_word}" if target_word else ""))
        game = ContextoGame()
        rooms[room_id] = {
            "game": game,
            "guesses": [], # List of guess objects
            "players": set(),
            "init_task": None
        }
        
        async def emit_progress(msg):
            await sio.emit("room_loading", {"msg": msg}, room=room_id)
            
        async def init_game():
            try:
                await game.initialize(target_word=target_word, emit_cb=emit_progress)
                await sio.emit("room_loading", {"msg": ""}, room=room_id)
            except Exception as e:
                print(f"Failed to initialize game for room {room_id}: {e}")
                
        rooms[room_id]["init_task"] = asyncio.create_task(init_game())
        
    await sio.enter_room(sid, room_id)
    rooms[room_id]["players"].add(player_name)
    sid_to_info[sid] = {"room_id": room_id, "player_name": player_name}
    
    # Notify room someone joined
    await sio.emit("player_joined", {
        "player_name": player_name,
        "players": list(rooms[room_id]["players"])
    }, room=room_id)
    
    if rooms[room_id]["init_task"]:
        await rooms[room_id]["init_task"]
    
    # Send current room state to the newly joined player
    await sio.emit("room_state", {
        "guesses": rooms[room_id]["guesses"],
        "total_words": len(rooms[room_id]["game"].ranked_vocab),
        "players": list(rooms[room_id]["players"])
    }, to=sid)

@sio.event
async def make_guess(sid, data):
    print(f"Received make_guess from {sid}: {data}")
    room_id = data.get("room_id")
    player_name = data.get("player_name")
    guess_word = data.get("guess")
    
    if not room_id or not guess_word:
        print("make_guess aborted: missing room_id or guess")
        return
        
    room = rooms.get(room_id)
    if not room:
        await sio.emit("error", {"msg": "Room not found"}, to=sid)
        return
        
    game = room["game"]
    try:
        result = game.process_guess(guess_word)
    except Exception as e:
        print("process_guess failed:", e)
        # print stack trace:
        import traceback
        traceback.print_exc()
        await sio.emit("error", {"msg": "Internal server error during guess"}, to=sid)
        return

    if "error" in result:
        await sio.emit("guess_error", {"msg": result["error"]}, to=sid)
        return
        
    # Valid guess, attach player info
    guess_entry = {
        "word": result["word"],
        "similarity": result["similarity"],
        "rank": result["rank"],
        "player_name": player_name,
        "is_correct": result["is_correct"]
    }
    
    if "top_10" in result:
        guess_entry["top_10"] = result["top_10"]
    
    # Check if word already guessed in this room to avoid duplicates
    if not any(g["word"] == guess_entry["word"] for g in room["guesses"]):
        room["guesses"].append(guess_entry)
        
    print("Emitting new_guess:", guess_entry, "to room:", room_id)
    # Broadcast to everyone in the room
    try:
        await sio.emit("new_guess", guess_entry, room=room_id)
        print("Emit success!")
    except Exception as e:
        print("Emit failed:", e)

@sio.event
async def request_hint(sid, data):
    room_id = data.get("room_id")
    player_name = data.get("player_name")
    
    if not room_id or not player_name:
        return
        
    room = rooms.get(room_id)
    if not room:
        return
        
    game = room["game"]
    
    best_rank = None
    for g in room["guesses"]:
        if g["rank"] is not None:
            if best_rank is None or g["rank"] < best_rank:
                best_rank = g["rank"]
                
    hint_word = game.get_hint_word(best_rank)
    if hint_word:
        await make_guess(sid, {
            "room_id": room_id,
            "player_name": player_name,
            "guess": hint_word
        })

app = sio_app

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
