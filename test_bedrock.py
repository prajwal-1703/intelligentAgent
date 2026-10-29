import json
import base64
import os
from dotenv import load_dotenv

# Force load variables from .env and clear any conflicting session tokens
load_dotenv(override=True)
if "AWS_SESSION_TOKEN" in os.environ:
    del os.environ["AWS_SESSION_TOKEN"]

from ai.bedrock_client import BedrockClient

def test_bedrock_text():
    print("Initializing BedrockClient...")
    client = BedrockClient()
    
    test_prompt3 = "capture the screen and tell me what is there"
    print(f"\nUser: '{test_prompt3}'")
    response3 = client.get_intent(test_prompt3)
    print("Agent JSON:", json.dumps(response3))

if __name__ == "__main__":
    print("--- AWS Bedrock Service Test ---")
    try:
        test_bedrock_text()
        print("\nTest completed successfully!")
    except Exception as e:
         print(f"\nFailed to connect or test AWS Bedrock: {e}")
         print("Make sure you have your AWS credentials configured properly (e.g., via 'aws configure' or environment variables).")
