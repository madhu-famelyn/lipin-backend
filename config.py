from dotenv import load_dotenv
import os
import json
from openai import OpenAI, AsyncOpenAI
import firebase_admin
from firebase_admin import credentials, firestore

load_dotenv()

# OpenAI
client = OpenAI()  # Sync client for backwards compatibility
async_client = AsyncOpenAI()  # Async client for parallel LLM calls

# Firebase - supports both file path (local) and JSON string (production)
firebase_config = os.getenv("FIREBASE_API", "firebase.json")

if firebase_config.startswith("{"):
    # JSON string from environment variable
    fireCred = credentials.Certificate(json.loads(firebase_config))
else:
    # File path
    fireCred = credentials.Certificate(firebase_config)

firebase_admin.initialize_app(fireCred)
db = firestore.client()
