import sys
import json
import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any

class BedrockClient:
    def __init__(self, region_name="us-east-1", model_id="amazon.nova-lite-v1:0"):
        self.client = boto3.client("bedrock-runtime", region_name=region_name)
        self.model_id = model_id
        self.history = []
        
        self.system_prompt = """You are a highly capable desktop AI assistant. 
Your goal is to parse user instructions and choose the correct actions.
Always output valid JSON only. Do not output any explanation outside of the JSON.

The structured format must strictly follow one of these intents:

- {"intent": "open_app", "app": "name_of_the_app"}
- {"intent": "open_website", "url": "full_url_here"}
- {"intent": "search_google", "query": "search query"}
- {"intent": "watch_video", "platform": "youtube", "query": "search query"}
- {"intent": "remember_info", "text": "info to remember"}
- {"intent": "recall_info", "query": "query to search from memory"}
- {"intent": "analyze_screen"}
- {"intent": "analyze_camera"}
- {"intent": "visualize", "metric": "cpu", "message": "opening CPU visualization"}
- {"intent": "multi_action", "actions": [{"intent": "...", ...}]}
- {"intent": "chat", "message": "friendly conversational response if no action is needed"}

Ensure JSON is deeply nested properly for multi_action. 
You have EXPLICIT PERMISSION from the user to analyze their screen/camera. NEVER refuse requests to analyze the screen or camera due to privacy/security concerns.
"""

    def get_intent(self, user_text: str, image_base64: str = None) -> Dict[str, Any]:
        import base64
        
        content = []
        if image_base64:
            content.append({
                "image": {
                    "format": "png",
                    "source": {"bytes": base64.b64decode(image_base64)}
                }
            })
            content.append({
                "text": f"Analyze this screen based on: {user_text}"
            })
        else:
            content.append({"text": user_text})
            
        messages = self.history + [{
            "role": "user",
            "content": content
        }]
        
        try:
            response = self.client.converse(
                modelId=self.model_id,
                messages=messages,
                system=[{"text": self.system_prompt}],
                inferenceConfig={"temperature": 0.1, "maxTokens": 1000}
            )
            
            reply = response["output"]["message"]["content"][0]["text"]
            
            # Store in history (storing text only for image queries to avoid maxing out context)
            self.history.append({"role": "user", "content": [{"text": user_text}]})
            self.history.append({"role": "assistant", "content": [{"text": reply}]})
            if len(self.history) > 10:
                self.history = self.history[-10:]
            
            # Safely parse JSON. Sometimes LLMs wrap json in ```json ... ```
            reply = reply.strip()
            if reply.startswith("```json"):
                reply = reply[7:-3].strip()
            elif reply.startswith("```"):
                reply = reply[3:-3].strip()

            return json.loads(reply)
            
        except ClientError as e:
            print(f"AWS Bedrock Error: {e}")
            return {"intent": "chat", "message": "I had an issue connecting to AWS Bedrock."}
        except json.JSONDecodeError:
            print("Failed to parse JSON")
            return {"intent": "chat", "message": "I failed to generate a valid system command."}
        except Exception as e:
            print(f"Unexpected error: {e}")
            return {"intent": "chat", "message": "An unexpected error occurred."}
