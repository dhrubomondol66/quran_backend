import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/voice/ws/recite?surah_number=1&ayah_start=1"
    
    print(f"🔄 Connecting to: {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")
            
            # Receive messages
            while True:
                message = await websocket.recv()
                data = json.loads(message)
                
                print(f"\n📨 Received message:")
                print(f"   Type: {data.get('type')}")
                print(f"   Data: {json.dumps(data, indent=2)}")
                
                if data.get('type') == 'ready':
                    print("\n✅ Server is ready for audio!")
                    break
    
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())