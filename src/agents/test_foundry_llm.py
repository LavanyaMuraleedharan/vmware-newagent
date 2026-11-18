
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from project root
load_dotenv()

client = OpenAI(
    api_key=os.getenv("FOUNDRY_API_KEY"),
    base_url=os.getenv("FOUNDRY_ENDPOINT")
)

response = client.responses.create(
    model=os.getenv("FOUNDRY_MODEL"),
    input="You are an Infrastructure FinOps AI assistant. Explain storage optimization in 3 points."
)

print("\nGPT-4.1 nano response:\n")
print(response.output_text)
