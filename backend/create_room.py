#!/usr/bin/env python3
"""
Create a custom game room with a specific target word.

Usage:
    python create_room.py <target_word>
    
Example:
    python create_room.py routine
"""

import sys
import random
import string
import socketio

def generate_room_code():
    """Generate a random 6-character room code."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

def create_room(target_word, room_code=None):
    """Create a room with the given target word and return the room code."""
    if room_code is None:
        room_code = generate_room_code()
    
    sio = socketio.Client()
    result = {"success": False, "room_code": room_code}
    
    @sio.event
    def connect():
        sio.emit('join_room', {
            'room_id': room_code,
            'player_name': 'room-creator',
            'target_word': target_word
        })
    
    @sio.event
    def room_state(data):
        if not data.get("ready"):
            return
        result["success"] = True
        result["total_words"] = data.get("total_words", 0)
        sio.disconnect()
    
    @sio.event
    def room_loading(data):
        if data.get('msg'):
            print(f"  {data['msg']}", file=sys.stderr)
    
    @sio.event
    def connect_error(data):
        print(f"Connection failed: {data}", file=sys.stderr)
        sio.disconnect()

    @sio.event
    def error(data):
        print(f"Server error: {data}", file=sys.stderr)
        sio.disconnect()
    
    try:
        sio.connect('http://localhost:8000', wait_timeout=10)
        sio.wait()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return None
    
    if result["success"]:
        return result
    return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python create_room.py <target_word> [room_code]")
        print("Example: python create_room.py routine")
        print("         python create_room.py routine my-custom-room")
        sys.exit(1)
    
    target_word = sys.argv[1].lower().strip()
    room_code = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"Creating room with target word: {target_word}")
    result = create_room(target_word, room_code)
    
    if result:
        print(f"\n{'='*40}")
        print(f"Room created successfully!")
        print(f"Room Code: {result['room_code']}")
        print(f"Target Word: {target_word}")
        print(f"Total Words: {result['total_words']}")
        print(f"{'='*40}")
        print(f"\nShare this room code with players: {result['room_code']}")
    else:
        print("Failed to create room. Is the server running?")
        sys.exit(1)

if __name__ == "__main__":
    main()
