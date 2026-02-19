from dotenv import load_dotenv
import os
from openai import OpenAI, AsyncOpenAI
import firebase_admin
from firebase_admin import credentials, firestore

load_dotenv()

# OpenAI
client = OpenAI()  # Sync client for backwards compatibility
async_client = AsyncOpenAI()  # Async client for parallel LLM calls

# Firebase
fireCred = credentials.Certificate(os.getenv("FIREBASE_API"))
firebase_admin.initialize_app(fireCred)
db = firestore.client()
