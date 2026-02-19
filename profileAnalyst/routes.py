from fastapi import APIRouter, HTTPException, FastAPI, Query
from pydantic import BaseModel
from .scraper import scrape_profile, setup_session
import threading
import asyncio
from lipInDashboard.helper import Clean_JSON
import json
import time
from config import db, async_client
from cache import get_cached_profile, set_cached_profile
from .prompts import ProfileScoringPrompt

router = APIRouter(prefix="/profile_analyst", tags=["Profile Analyst"])


class ScrapeRequest(BaseModel):
    profile_url: str
    headless: bool = True


@router.post("/scrape")
def scrape(req: ScrapeRequest):
    """Scrape a LinkedIn profile and return structured data."""
    try:
        data = scrape_profile(req.profile_url, headless=req.headless)
        if data:
            doc_id = req.profile_url.rstrip("/").split("/")[-1]
            _, doc_ref = db.collection("users").document(doc_id).collection('profileInfo').add(data)
        return {"success": True, "data": data,
                "document_id": doc_ref.id, "message": "Profile scraped and added to database successfully."
                }
    except RuntimeError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


@router.get("/setup")
def run_setup():
    """
    Trigger browser session setup.
    Opens a headed browser — you must be running this locally.
    This runs in a background thread so the API doesn't block.
    """
    def _setup():
        setup_session()

    thread = threading.Thread(target=_setup)
    thread.start()
    return {
        "message": "Browser opened. Log in with Google in the browser window, then press ENTER in the terminal."
    }


# Profile Scoring Endpoint
@router.get("/score_profile")
async def score_profile(profile_url: str = Query(...)):
    start_time = time.time()
    print(f"[score_profile] Request started for: {profile_url}")

    # Check cache first
    cache_start = time.time()
    cache_key = f"score:{profile_url.strip()}"
    cached_data = await get_cached_profile(cache_key)
    cache_time = time.time() - cache_start
    print(f"[score_profile] Cache check took: {cache_time:.3f}s")

    if cached_data:
        total_time = time.time() - start_time
        print(f"[score_profile] Cache HIT - Total time: {total_time:.3f}s")
        return {"success": True, "data": cached_data}

    # Run Firestore call in thread pool to avoid blocking event loop
    def fetch_profile_data():
        data_ref = (db.collection("users").document(profile_url.strip())
                .collection("profileInfo")
                .stream())
        return [doc.to_dict() for doc in data_ref]

    profile_data = await asyncio.to_thread(fetch_profile_data)
    if not profile_data:
        raise HTTPException(status_code=404, detail="Profile data not found. Please scrape the profile first.")
    doc = profile_data[0]
    print(f"[score_profile] Doc keys: {list(doc.keys())}")

    basic_info = doc.get('basic_info', {})
    about = doc.get('about', '')
    experience = doc.get('experience', [])
    skills = doc.get('skills', [])
    profile_picture = basic_info.get('profile_picture_url', '')
    education = doc.get('education', [])
    certification = doc.get('certifications', [])
    headline = basic_info.get('headline', '')
    network_size = basic_info.get('connections', '')
    recent_posts = doc.get('recent_posts', [])

    print(f"[score_profile] Data: headline='{headline[:50] if headline else 'None'}', about={len(about) if about else 0} chars, exp={len(experience)}, skills={len(skills)}, connections={network_size}")

    # Check if we have enough data to score
    if not headline and not about and not experience:
        print(f"[score_profile] WARNING: No meaningful data found in profile")
        return {"success": True, "data": {"section_scores": [], "error": "No profile data found - profile may need to be scraped first"}}

    # Truncate data for faster processing
    about_short = about[:500] if about else ''
    experience_short = experience[:3] if experience else []
    skills_short = skills[:10] if skills else []
    recent_posts_short = recent_posts[:2] if recent_posts else []

    score_prompt = ProfileScoringPrompt(about_short, headline, certification, experience_short, skills_short, education, profile_picture, network_size, recent_posts_short)

    # Use async LLM call with optimized params
    llm_start = time.time()
    response = await async_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=score_prompt.generate_prompt(),
        timeout=60,
        max_tokens=2500,  # Reduced - condensed prompt needs fewer output tokens
        temperature=0.05,  # Lower temp = faster, more deterministic
        response_format={"type": "json_object"}
    )
    llm_time = time.time() - llm_start
    print(f"[score_profile] LLM call took: {llm_time:.3f}s")

    formatted_response = response.choices[0].message.content
    print(f"Score profile raw response length: {len(formatted_response)}")

    final_response = Clean_JSON(formatted_response)
    cleaned_response = final_response.clean_json_response()

    try:
        parsed_profile_builder = json.loads(cleaned_response)
        print(f"Score profile parsed keys: {list(parsed_profile_builder.keys())}")
    except json.JSONDecodeError as e:
        print(f"Score profile JSON parse error: {e}")
        print(f"Cleaned response: {cleaned_response[:500]}")
        raise HTTPException(500, f"Failed to parse score profile response: {str(e)}")
    # Override current fields with exact scraped data
    section_scores = parsed_profile_builder.get("section_scores", [])
    for section in section_scores:
        section_name = (section.get("section_name") or "").lower()
        if "visual branding" in section_name:
            section["current"] = {
                "profile_picture": profile_picture,
                "has_custom_banner": bool(basic_info.get("banner_url"))
            }
        elif "headline" in section_name:
            section["current"] = headline
        elif "about" in section_name:
            section["current"] = about
        elif "experience" in section_name:
            section["current"] = experience
        elif "skills" in section_name:
            skills_list = skills if isinstance(skills, list) else []
            section["current"] = {
                "skills_count": len(skills_list),
                "skills": skills_list,
                "top_endorsed": []
            }
        elif "recommendations" in section_name:
            section["current"] = {
                "count": len(doc.get("recommendations", []) or []),
                "most_recent": doc.get("recommendations_meta", {}).get("most_recent", ""),
                "sources": doc.get("recommendations_meta", {}).get("sources", [])
            }
        elif "network" in section_name:
            section["current"] = {
                "connections": network_size,
                "visible_count": network_size if isinstance(network_size, int) else None
            }
        elif "activity" in section_name or "engagement" in section_name:
            section["current"] = {
                "post_count": len(recent_posts) if recent_posts else 0
            }
    parsed_profile_builder["section_scores"] = section_scores

    # Only cache if data is valid (has section_scores with content)
    if section_scores and len(section_scores) > 0:
        await set_cached_profile(cache_key, parsed_profile_builder)
        print(f"[score_profile] Data cached successfully")
    else:
        print(f"[score_profile] WARNING: Not caching - empty or invalid data")

    total_time = time.time() - start_time
    print(f"[score_profile] Total request time: {total_time:.3f}s (LLM: {llm_time:.3f}s)")

    return {"success": True, "data": parsed_profile_builder}

# Standalone mode for testing without main app
if __name__ == "__main__":
    import uvicorn
    app = FastAPI(title="LinkedIn Profile Scraper API")
    app.include_router(router)
    uvicorn.run(app, host="127.0.0.1", port=8001)
