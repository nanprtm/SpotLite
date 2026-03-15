"""Test that mimics actual app flow - receive loop running in background."""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

LIVE_MODEL = "gemini-live-2.5-flash-native-audio"


async def main():
    client = genai.Client(
        vertexai=True,
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
            )
        ),
        system_instruction=types.Content(
            parts=[types.Part(text="You are a helpful assistant. Greet the user briefly.")]
        ),
        tools=[{"function_declarations": [
            {"name": "test_func", "description": "Test",
             "parameters": {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}}
        ]}],
    )

    # Mimic what the app does: manual __aenter__ + background receive task
    print(f"Connecting to {LIVE_MODEL}...")
    ctx = client.aio.live.connect(model=LIVE_MODEL, config=config)
    session = await ctx.__aenter__()
    print("Session opened via __aenter__")

    async def receive_loop():
        try:
            msg_count = 0
            async for msg in session.receive():
                msg_count += 1
                parts_info = []
                if msg.server_content:
                    sc = msg.server_content
                    if sc.model_turn:
                        for p in sc.model_turn.parts:
                            if p.inline_data:
                                parts_info.append(f"audio({len(p.inline_data.data)}b)")
                            if p.text:
                                parts_info.append(f"text({p.text[:50]})")
                    if sc.turn_complete:
                        parts_info.append("turn_complete")
                    if sc.interrupted:
                        parts_info.append("interrupted")
                if msg.tool_call:
                    for fc in msg.tool_call.function_calls:
                        parts_info.append(f"tool_call({fc.name})")
                if msg.tool_call_cancellation:
                    parts_info.append("tool_call_cancellation")

                print(f"  msg#{msg_count}: [{', '.join(parts_info) or 'empty'}]")

            print(f"Receive loop ended naturally after {msg_count} messages")
        except asyncio.CancelledError:
            print("Receive loop cancelled")
        except Exception as e:
            print(f"Receive loop error: {type(e).__name__}: {e}")

    task = asyncio.create_task(receive_loop())
    print("Receive loop task started, waiting 10 seconds...")

    for i in range(10):
        await asyncio.sleep(1)
        if task.done():
            print(f"Task ended at second {i+1}!")
            break
        else:
            print(f"  ...second {i+1}, still alive")

    if not task.done():
        print("Session stayed open for 10s! Cleaning up...")
        task.cancel()

    try:
        await ctx.__aexit__(None, None, None)
    except Exception:
        pass
    print("Done")


if __name__ == "__main__":
    asyncio.run(main())
