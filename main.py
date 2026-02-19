import sys
import os

# Ensure lipInBackEnd/ root is on sys.path so submodules can import
# top-level modules (config, prompts, helper, etc.)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import config  # noqa: F401 — triggers Firebase + OpenAI init
_ = config  # ensure import is not pruned

from lipInDashboard.routes import router as dashboard_router
from profileAnalyst.routes import router as profile_router

app = FastAPI()

origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "https://lipin.onrender.com",
    "https://lipindashboard.netlify.app",
    "https://myfrontenddomain.com",
    "chrome-extension://*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origin_regex=r"^chrome-extension://.*$",
)

# Mount routers
app.include_router(dashboard_router)
app.include_router(profile_router)


@app.get("/")
async def welcome():
    return {"message": "Welcome to the LipIn BackEnd API!"}


@app.delete("/clear-cache")
async def clear_cache():
    from cache import clear_all_cache
    deleted = clear_all_cache()
    return {"success": True, "message": f"Cleared {deleted} cached entries"}


if __name__ == "__main__":
    import os
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
