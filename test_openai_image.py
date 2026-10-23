from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

print("🧠 Testing OpenAI Image API...")

try:
    response = client.images.generate(
        model="dall-e-3",
        prompt="A realistic digital painting of a sunny sky over mountains",
        size="1024x1024"
    )
    print("✅ Success! Here's the image URL:")
    print(response.data[0].url)
except Exception as e:
    print("❌ Error:")
    print(e)
