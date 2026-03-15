"""Quick test: verify image generation works with gemini-2.5-flash-image."""
import asyncio
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

async def main():
    client = genai.Client(
        vertexai=True,
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )

    print("Generating image with gemini-2.5-flash-image...")
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash-image",
        contents="Create a picture of a nano banana dish in a fancy restaurant with a Gemini theme",
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    for part in response.candidates[0].content.parts:
        if part.text:
            print(f"Text: {part.text}")
        if part.inline_data:
            ext = part.inline_data.mime_type.split("/")[-1]
            filename = f"test_output.{ext}"
            with open(filename, "wb") as f:
                f.write(part.inline_data.data)
            print(f"Image saved to {filename} ({len(part.inline_data.data)} bytes)")

    print("Done!")

asyncio.run(main())
