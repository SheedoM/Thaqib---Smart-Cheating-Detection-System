import asyncio
import websockets
import json

async def simulate_client(client_id, target_id=None, delay=0):
    uri = f"ws://localhost:8000/api/v1/ptt/ws/{client_id}"
    await asyncio.sleep(delay)  # Stagger connections
    
    async with websockets.connect(uri) as websocket:
        print(f"[{client_id}] Connected to PTT Server")
        
        # Listener Task
        async def listen():
            try:
                while True:
                    response = await websocket.recv()
                    print(f"[{client_id}] Received: {response}")
            except websockets.exceptions.ConnectionClosed:
                print(f"[{client_id}] Connection Closed")
                
        listener_task = asyncio.create_task(listen())
        
        # Sender Logic
        if target_id:
            print(f"[{client_id}] Sending 'start_speak' to {target_id}...")
            await websocket.send(json.dumps({
                "type": "start_speak",
                "target_id": target_id
            }))
            await asyncio.sleep(2)
            print(f"[{client_id}] Sending 'stop_speak' to {target_id}...")
            await websocket.send(json.dumps({
                "type": "stop_speak",
                "target_id": target_id
            }))
            
        await asyncio.sleep(5)  # Keep connection open for a bit to listen
        listener_task.cancel()

async def main():
    print("Starting PTT Simulation...")
    print("Ensure the FastAPI server is running: uvicorn src.thaqib.main:app --reload")
    
    # Simulate Control Room entering first
    task_control = asyncio.create_task(simulate_client("control_room_1", delay=0))
    
    # Simulate Invigilator 1 entering and speaking to Control Room
    task_invig1 = asyncio.create_task(simulate_client("invigilator_1", target_id="control_room_1", delay=1))
    
    # Simulate Invigilator 2 entering and broadcasting to all (no target)
    task_invig2 = asyncio.create_task(simulate_client("invigilator_2", target_id=None, delay=2))

    await asyncio.gather(task_control, task_invig1, task_invig2)
    print("Simulation Complete.")

if __name__ == "__main__":
    asyncio.run(main())
