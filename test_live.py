"""Minimal test to debug Gemini Live API connection."""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

LIVE_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"


async def test_minimal():
    """Test 1: Bare minimum config - no tools, no system instruction."""
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    print(f"API key present: {bool(os.getenv('GOOGLE_API_KEY'))}")
    print(f"API key prefix: {os.getenv('GOOGLE_API_KEY', '')[:10]}...")
    print(f"\n--- Test 1: Minimal config (audio only) ---")
    try:
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
        )
        async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            print("SUCCESS: Session connected!")
            print("Waiting 3 seconds to see if it stays open...")
            await asyncio.sleep(3)
            print("Session still open after 3s!")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")


async def test_with_system_instruction():
    """Test 2: Add system instruction as plain string."""
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    print(f"\n--- Test 2: With system instruction (string) ---")
    try:
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction="You are a helpful assistant. Say hello.",
        )
        async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            print("SUCCESS: Session connected with system instruction!")
            await asyncio.sleep(3)
            print("Session still open after 3s!")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")


async def test_with_tools():
    """Test 3: Add tools."""
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    print(f"\n--- Test 3: With tools ---")
    tools = [{"function_declarations": [
        {"name": "test_func", "description": "A test function",
         "parameters": {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}}
    ]}]
    try:
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            tools=tools,
        )
        async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            print("SUCCESS: Session connected with tools!")
            await asyncio.sleep(3)
            print("Session still open after 3s!")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")


async def test_with_voice():
    """Test 4: Add voice config."""
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    print(f"\n--- Test 4: With voice config ---")
    try:
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
                )
            ),
        )
        async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            print("SUCCESS: Session connected with voice!")
            await asyncio.sleep(3)
            print("Session still open after 3s!")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")


async def test_full():
    """Test 5: Full config like our app uses."""
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    print(f"\n--- Test 5: Full config (like app) ---")
    tools = [{"function_declarations": [
        {"name": "generate_stage_image", "description": "Generate image",
         "parameters": {"type": "object", "properties": {"description": {"type": "string"}}, "required": ["description"]}}
    ]}]
    try:
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part(text="You are a helpful stage design assistant.")]
            ),
            tools=tools,
        )
        async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            print("SUCCESS: Full config session connected!")
            await asyncio.sleep(3)
            print("Session still open after 3s!")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")


async def main():
    await test_minimal()
    await test_with_system_instruction()
    await test_with_tools()
    await test_with_voice()
    await test_full()
    print("\n--- All tests done ---")

if __name__ == "__main__":
    asyncio.run(main())
