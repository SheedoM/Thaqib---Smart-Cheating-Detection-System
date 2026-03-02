import asyncio
import websockets
import json
import sys

async def listen(websocket, client_id):
    try:
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            sender = data.get("sender_id", "System")
            msg_type = data.get("type", "Unknown")
            print(f"\n\n🔔 [RECEIVED from {sender}] Action: {msg_type}")
            print(f"[{client_id}] > ", end="", flush=True)
    except websockets.exceptions.ConnectionClosed:
        print("\nConnection closed by the server.")

async def send(websocket, client_id):
    loop = asyncio.get_event_loop()
    while True:
        # Run input() in executor to avoid blocking the asyncio event loop
        user_input = await loop.run_in_executor(None, input, f"[{client_id}] > ")
        if not user_input:
            continue
        
        parts = user_input.strip().split()
        cmd = parts[0].lower()
        
        if cmd == "quit" or cmd == "exit":
            break
            
        if cmd not in ["start", "stop"]:
            print("Commands: 'start <target_id>', 'stop <target_id>', 'start all', 'quit'")
            continue
            
        target_id = parts[1] if len(parts) > 1 else None
        
        if target_id == "all":
            target_id = None
            
        msg_type = f"{cmd}_speak"

        payload = {
            "type": msg_type,
            "target_id": target_id
        }
        
        await websocket.send(json.dumps(payload))
        target_str = target_id if target_id else "EVERYONE"
        print(f"🎤 -> Sent '{msg_type}' to {target_str}")

async def main():
    print("="*40)
    print("   Thaqib PTT Interactive CLI")
    print("="*40)
    client_id = input("Enter your Client ID (e.g., control_room, invigilator_1): ").strip()
    if not client_id:
        client_id = "test_user"
        
    uri = f"ws://127.0.0.1:8000/api/v1/ptt/ws/{client_id}"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"\n✅ Connected to Server as '{client_id}'.")
            print("\nAvailable Commands: ")
            print("  start <target_id>  (e.g., start invigilator_1)")
            print("  stop <target_id>   (e.g., stop invigilator_1)")
            print("  start all          (Broadcasts to everyone)")
            print("  quit               (Exit the client)")
            print("-" * 40)
            
            listener_task = asyncio.create_task(listen(websocket, client_id))
            sender_task = asyncio.create_task(send(websocket, client_id))
            
            done, pending = await asyncio.wait(
                [listener_task, sender_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            
            for task in pending:
                task.cancel()
                
    except ConnectionRefusedError:
        print("\n❌ Failed to connect. Is the FastAPI server running?")
        print("Run matching server with: uvicorn src.thaqib.main:app")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
