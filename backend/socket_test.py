import socketio
import time

sio = socketio.Client()

@sio.event
def connect():
    print("Test Client connected.")
    sio.emit('join_room', {'room_id': 'TESTROOM', 'player_name': 'Tester'})

@sio.event
def room_state(data):
    if not data.get("ready"):
        return
    print("Received room state with", len(data.get('guesses', [])), "guesses")
    print("Making a guess now...")
    sio.emit('make_guess', {'room_id': 'TESTROOM', 'player_name': 'Tester', 'guess': 'apple'})

@sio.event
def room_loading(data):
    if data.get("msg"):
        print("Loading:", data.get("msg"))

@sio.event
def new_guess(data):
    print("Received new guess instantly:", data)
    sio.disconnect()

@sio.event
def disconnect():
    print("Disconnected.")

if __name__ == '__main__':
    sio.connect('http://localhost:8000')
    sio.wait()
