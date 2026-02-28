"""
Test that the Semantle game selects meaningful target words.
This test connects via Socket.IO and verifies that room creation
results in meaningful target words (not function words like 'the', 'a', 'is').
"""
import os
import socketio
import sys
import time
import threading

# Words that should NEVER be selected as targets
FUNCTION_WORDS = {
    "the", "a", "an", "in", "on", "at", "is", "are", "was", "be", 
    "and", "but", "or", "he", "she", "it", "you", "we", "to", "of", 
    "for", "by", "with", "as", "if", "no", "so", "up", "out", "this",
    "that", "these", "those", "has", "have", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "can", "not"
}

def test_room_creation():
    """
    Integration smoke test: can we connect, join, and eventually receive a ready room_state?

    Note: the server intentionally does not expose the actual target word to clients, so this
    test cannot directly assert "meaningful" vs "function word". That behavior is covered by
    the pure-python tests in `test_logic.py` (meaningful vocab filter + random selection).
    """
    server_url = os.environ.get("SERVER_URL", "http://localhost:8000")
    print(f"=== Testing Room Creation via Socket.IO ({server_url}) ===\n", flush=True)

    results = []

    for i in range(5):
        room_id = f"TEST_ROOM_{i}_{time.time()}"
        sio = socketio.Client()
        got_any_state = threading.Event()
        got_ready_state = threading.Event()

        @sio.event
        def connect():
            sio.emit("join_room", {"room_id": room_id, "player_name": "Tester"})

        @sio.event
        def room_state(data):
            got_any_state.set()
            ready = bool(data.get("ready"))
            total_words = data.get("total_words")
            print(f"  Room {room_id}: room_state ready={ready} total_words={total_words}", flush=True)
            if ready:
                got_ready_state.set()

        @sio.event
        def room_loading(data):
            if data.get("msg"):
                print(f"  Room {room_id}: loading - {data.get('msg')}", flush=True)

        @sio.event
        def connect_error(data):
            print(f"  Room {room_id}: connect_error - {data}", flush=True)

        try:
            # Prefer websocket transport: it's significantly more reliable than polling
            # for long-running init workloads on localhost.
            sio.connect(server_url, wait_timeout=20, transports=["websocket"])

            if not got_any_state.wait(timeout=10):
                raise TimeoutError("Timed out waiting for first room_state")

            if not got_ready_state.wait(timeout=60):
                raise TimeoutError("Timed out waiting for ready room_state")

            results.append({"room_id": room_id, "success": True})
        except Exception as e:
            print(f"  Room {room_id}: Error - {e}", flush=True)
            results.append({"room_id": room_id, "success": False, "error": str(e)})
        finally:
            try:
                sio.disconnect()
            except Exception:
                pass
            time.sleep(0.5)

    print("\n=== Results ===", flush=True)
    success_count = sum(1 for r in results if r["success"])
    print(f"Successfully created {success_count}/{len(results)} rooms", flush=True)

    if success_count == len(results):
        print("\n✅ All Socket.IO room creation tests passed!", flush=True)
        return True

    print("\n❌ Some tests failed", flush=True)
    return False

if __name__ == "__main__":
    success = test_room_creation()
    sys.exit(0 if success else 1)
