from fastapi import APIRouter, HTTPException, status, File, UploadFile, Form, Query
from pydantic import BaseModel
from typing import List, Optional
import json
import base64
import io
import time
import asyncio
from PyPDF2 import PdfReader
from config import db, client, async_client
from cache import get_cached_profile, set_cached_profile
from llm_utils import single_llm_call
from .prompts import (
    Comments,
    SSIRecommendations,
    SSIImageProcessing,
    NicheRecommendation,
    NicheSpecificRecommendation,
    PostGenPrompt,
    ProfileBuilderPrompt,
)
from .helper import Image_Processor, Clean_JSON, File_to_Base64, Simple_File_Handler

router = APIRouter(tags=["Dashboard"])

# ──────────────────────────────────────────────
# Pydantic Models
# ──────────────────────────────────────────────

class CommentsBody(BaseModel):
    post: str
    prompt: str | None = None
    tone: str | None = None
    persona: str | None = None
    language: str | None = None

class GeneratePostInput(BaseModel):
    profile_url: str
    prompt: str
    tone: str | None = None
    language: str | None = None
    attachments: Optional[List[UploadFile]] = File(None)
    history: List[str] = []

class profileLink(BaseModel):
    profile_url: str

class nicheRecommend(BaseModel):
    profile_url: str
    niche: str

class PostBody(BaseModel):
    userReq: str

class GoogleSignInRequest(BaseModel):
    profileURL: str

class AskAIChat(BaseModel):
    message: str
    history: List[str] = []
    profile_url: Optional[str] = None

class GoogleSignInResponse(BaseModel):
    message: str

class SelectedNicheRequest(BaseModel):
    profile_url: str
    niche: str

# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@router.post("/postGenerator")
async def generate_post(
    profile_url: str = Form(...),
    prompt: str = Form(...),
    tone: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    history: List[str] = Form([]),
    attachments: Optional[List[UploadFile]] = File(None)
):
    tone = tone if tone else "Professional, positive, conversational tone"
    language = language if language else 'Use American English with plain, conversational language. Short sentences, common vocabulary, American spelling (color, organize), friendly and easy to understand.'

    processed_attachments = []
    if attachments:
        file_cvt = File_to_Base64()
        for file in attachments:
            if hasattr(file, 'filename') and file.filename:
                try:
                    file_content = await file.read()
                    file_size = len(file_content)
                    await file.seek(0)

                    if Simple_File_Handler.should_use_base64(file_size):
                        converted_file = await file_cvt.file_to_base64(file)
                        processed_attachments.append(converted_file)
                    else:
                        file_summary = Simple_File_Handler.get_file_summary(file, file_size)
                        processed_attachments.append({
                            "filename": file.filename,
                            "content_type": getattr(file, 'content_type', 'unknown'),
                            "size": file_size,
                            "summary": file_summary,
                            "type": "file_summary"
                        })
                except Exception as e:
                    processed_attachments.append({
                        "filename": getattr(file, 'filename', 'unknown'),
                        "error": f"File processing failed: {str(e)}",
                        "type": "error"
                    })

    genPostSystem = PostGenPrompt(processed_attachments, tone, language)
    try:
        messages = [{"role": "system", "content": genPostSystem.generate_prompt()}]
        for i, msg in enumerate(history):
            if i % 2 == 0:
                messages.append({"role": "user", "content": msg})
            else:
                messages.append({"role": "assistant", "content": msg})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=1000,
            n=1,
            stop=None,
            temperature=0.7,
        )
        aiResponse = response.choices[0].message.content.strip()
        print(aiResponse)
        return {"response": aiResponse}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profileBuilder")
async def get_profile_builder(profile_url: str = Query(...), niche: str = Query(None)):
    start_time = time.time()
    print(f"[profileBuilder] Request started for: {profile_url}, niche: {niche}")

    try:
        # Check cache first
        cache_start = time.time()
        cache_key = f"profile_builder:{profile_url.strip()}:{niche or 'general'}"
        cached_data = await get_cached_profile(cache_key)
        cache_time = time.time() - cache_start
        print(f"[profileBuilder] Cache check took: {cache_time:.3f}s")

        if cached_data:
            total_time = time.time() - start_time
            print(f"[profileBuilder] Cache HIT - Total time: {total_time:.3f}s")
            return {"success": True, "message": "Data retrieved from cache", "data": cached_data}

        # Run Firestore calls in thread pool to avoid blocking event loop
        def fetch_profile_info():
            data_ref = (db.collection("users").document(profile_url.strip())
                .collection("profileInfo")
                .stream())
            return [doc.to_dict() for doc in data_ref]

        def fetch_personal_info():
            doc_ref = (
                db.collection("users")
                .document(profile_url.strip())
                .collection("personalInfo")
                .stream()
            )
            return [d.to_dict() for d in doc_ref]

        # Fetch both in parallel using threads
        profile_data, documents = await asyncio.gather(
            asyncio.to_thread(fetch_profile_info),
            asyncio.to_thread(fetch_personal_info)
        )

        if not profile_data:
            raise HTTPException(404, "Profile data not found. Please scrape the profile first.")
        profile_doc = profile_data[0]

        if not documents:
            raise HTTPException(404, "Personal info not found. Please complete the onboarding form first.")

        parsed_profile_builder = None
        for doc in documents:
            headline = doc.get("headline")
            purpose = doc.get("purpose")
            currentExp = profile_doc.get('experience', [])
            about = doc.get("userDescription")
            topic_files = doc.get("topicsFiles")
            topics = []
            if topic_files:
                for topic in topic_files:
                    topics.append(topic)
            skills_files = profile_doc.get("skills", [])
            skills = []
            if skills_files:
                for skill in skills_files:
                    skills.append(skill)
            career = doc.get("careerVision")
            Niche = None
            if doc.get("niche"):
                Niche = doc.get("niche")
            else:
                Niche = niche
            profileSysIns = ProfileBuilderPrompt()

            ssi_files = doc.get("ssiScoreFiles")
            cleaned_response = {}
            if ssi_files:
                for idx, img in enumerate(ssi_files):
                    try:
                        content_type = img.get("content_type", "image/jpeg")
                        image_type = content_type.split("/")[-1] if "/" in content_type else "jpeg"

                        if image_type not in ["jpeg", "jpg", "png", "gif", "webp"]:
                            image_type = "jpeg"

                        base64_data = img.get("base64", "")
                        if not base64_data:
                            continue

                        data_uri = f"data:image/{image_type};base64,{base64_data}"
                    except Exception as e:
                        print(f"Error processing SSI image {idx}: {e}")
                        continue
            try:
                # Build user prompt with profile data
                full_prompt = f"""Generate optimized LinkedIn profile content based on this data:

PURPOSE: {purpose if purpose else 'N/A'}
CAREER GOALS: {career if career else 'N/A'}
CURRENT HEADLINE: {headline if headline else 'N/A'}
CURRENT ABOUT: {about if about else 'N/A'}
SKILLS: {', '.join(skills) if skills else 'None'}
TOPICS OF INTEREST: {', '.join(topics) if topics else 'None'}
CURRENT EXPERIENCE: {json.dumps(currentExp[:3]) if currentExp else 'None'}
TARGET NICHE: {Niche or 'General'}

Generate the complete profile builder JSON with all sections: headline, about, experience, skills, education, and recommendation_request_template.
Include "current" field with the user's actual data and "suggestions" array with improvements."""

                # Use async LLM call
                llm_start = time.time()
                response = await async_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        profileSysIns.generate_prompt(),
                        {
                            "role": "user",
                            "content": full_prompt
                        }
                    ],
                    timeout=120,
                    max_tokens=6000,
                    temperature=0.2,
                    response_format={"type": "json_object"}
                )
                llm_time = time.time() - llm_start
                print(f"[profileBuilder] LLM call took: {llm_time:.3f}s")

                raw_content = response.choices[0].message.content
                print(f"Raw OpenAI response length: {len(raw_content)}")
                print(f"Raw OpenAI response preview: {raw_content[:500]}...")

                try:
                    # With response_format=json_object, OpenAI guarantees valid JSON
                    parsed_response = json.loads(raw_content)
                    print(f"Parsed response keys: {list(parsed_response.keys())}")

                    # The prompt returns with a "data" wrapper, extract it
                    if "data" in parsed_response:
                        parsed_profile_builder = parsed_response["data"]
                    else:
                        parsed_profile_builder = parsed_response

                    print(f"Final profile builder keys: {list(parsed_profile_builder.keys())}")
                except json.JSONDecodeError as e:
                    print(f"Error parsing profile builder JSON: {e}")
                    print(f"Raw response: {raw_content}")
                    # Return a default structure instead of failing
                    parsed_profile_builder = {
                        "headline": {"current": headline or "", "suggestions": []},
                        "about": {"current": about or "", "suggestions": []},
                        "experience": {"positions": []},
                        "skills": {"current": skills or [], "skillsToPrioritize": []},
                        "error": "Failed to generate AI recommendations. Please try again."
                    }

                # Post-processing: Inject actual user data from Firebase into "current" fields
                # This ensures the response contains real user data, not LLM-generated content
                if "headline" in parsed_profile_builder:
                    if isinstance(parsed_profile_builder["headline"], dict):
                        parsed_profile_builder["headline"]["current"] = headline or ""
                    else:
                        parsed_profile_builder["headline"] = {"current": headline or "", "suggestions": parsed_profile_builder.get("headline", [])}

                if "about" in parsed_profile_builder:
                    if isinstance(parsed_profile_builder["about"], dict):
                        parsed_profile_builder["about"]["current"] = about or ""
                    else:
                        parsed_profile_builder["about"] = {"current": about or "", "suggestions": parsed_profile_builder.get("about", [])}

                if "experience" in parsed_profile_builder:
                    if isinstance(parsed_profile_builder["experience"], dict):
                        # Keep the LLM-generated suggestions in "positions" 
                        parsed_profile_builder["experience"]["current"] = currentExp or []
                        # Ensure positions key exists
                        if "positions" not in parsed_profile_builder["experience"]:
                            parsed_profile_builder["experience"]["positions"] = []
                    else:
                        # If experience is not a dict (shouldn't happen), create proper structure
                        parsed_profile_builder["experience"] = {
                            "current": currentExp or [], 
                            "positions": parsed_profile_builder.get("experience", []) if isinstance(parsed_profile_builder.get("experience"), list) else []
                        }

                if "skills" in parsed_profile_builder:
                    if isinstance(parsed_profile_builder["skills"], dict):
                        parsed_profile_builder["skills"]["current"] = skills or []
                    else:
                        parsed_profile_builder["skills"] = {"current": skills or [], "skillsToPrioritize": parsed_profile_builder.get("skills", [])}

            except Exception as e:
                print(f"Error generating profile builder data: {e}")
                raise HTTPException(500, f"Error generating profile builder data: {str(e)}")

        if parsed_profile_builder is None:
            raise HTTPException(500, "Failed to generate profile builder data")

        # Only cache if data is valid (has headline or about or experience)
        has_valid_data = (
            parsed_profile_builder.get("headline") or
            parsed_profile_builder.get("about") or
            parsed_profile_builder.get("experience")
        )
        if has_valid_data:
            await set_cached_profile(cache_key, parsed_profile_builder)
            print(f"[profileBuilder] Data cached successfully")
        else:
            print(f"[profileBuilder] WARNING: Not caching - empty or invalid data")

        total_time = time.time() - start_time
        print(f"[profileBuilder] Total request time: {total_time:.3f}s (LLM: {llm_time:.3f}s)")

        return {"success": True, "message": "Profile data fetched successfully", "data": parsed_profile_builder}

    except HTTPException:
        raise
    except Exception as e:
        print("ERROR:", e)
        raise HTTPException(500, f"Error fetching profile data: {str(e)}")


@router.get("/profileAnalysis")
async def get_personal_info(profile_url: str = Query(...)):
    start_time = time.time()
    print(f'[profileAnalysis] API called for: {profile_url}')
    try:
        if not profile_url or profile_url.strip() == "":
            raise HTTPException(400, "Profile URL cannot be empty")

        # Check cache first
        cached_data = await get_cached_profile(f"analysis:{profile_url.strip()}")
        if cached_data:
            print(f"[profileAnalysis] Cache hit - {time.time() - start_time:.2f}s")
            return {"success": True, "message": "Data retrieved from cache", "data": cached_data}

        # Run Firestore call in thread pool to avoid blocking
        def fetch_personal_info():
            doc_ref = (
                db.collection("users")
                .document(profile_url.strip())
                .collection("personalInfo")
                .stream()
            )
            return [d.to_dict() for d in doc_ref]

        documents = await asyncio.to_thread(fetch_personal_info)
        print(f"[profileAnalysis] Firestore fetch took: {time.time() - start_time:.2f}s")

        # Check if any documents were found
        if not documents:
            return {
                "success": False,
                "message": "No personal information found for this profile",
                "error": "No documents found in personalInfo collection"
            }

        # Initialize combined_result outside the loop
        combined_result = {"niche_recommendations": None}

        for doc in documents:
            headline = doc.get("headline")
            currentExp = doc.get("currentExp")
            pastExp = doc.get("pastExperience")
            about = doc.get("userDescription")
            topic_files = doc.get("topicsFiles")
            topics = []
            if topic_files:
                for topic in topic_files:
                    topics.append(topic)
            skills_files = doc.get("skillsFiles")
            skills = []
            if skills_files:
                for skill in skills_files:
                    skills.append(skill)
            career = doc.get("careerVision")

            ssi_files = doc.get("ssiScoreFiles")
            resume = doc.get("resumeFiles")
            processed_resume = []
            if resume:
                for file_data in resume:
                    if isinstance(file_data, dict) and "base64" in file_data:
                        try:
                            pdf_bytes = base64.b64decode(file_data["base64"])
                            pdf_file = io.BytesIO(pdf_bytes)

                            pdf_reader = PdfReader(pdf_file)
                            text_content = ""
                            for page in pdf_reader.pages:
                                text_content += page.extract_text() + "\n"

                            processed_resume.append({
                                "filename": file_data.get("filename", "resume.pdf"),
                                "content": text_content.strip(),
                                "type": "pdf_text_extracted"
                            })
                        except Exception as e:
                            print(f"Error extracting PDF text: {e}")
                            processed_resume.append({
                                "filename": file_data.get("filename", "unknown"),
                                "error": f"PDF extraction failed: {str(e)}",
                                "type": "error"
                            })
                    elif isinstance(file_data, dict) and "content" in file_data and "base64" not in file_data:
                        processed_resume.append(file_data)
                    elif isinstance(file_data, str) and not file_data.startswith("data:"):
                        processed_resume.append({
                            "content": file_data,
                            "type": "resume_data"
                        })
                    else:
                        print(f"Skipping resume item - might contain base64: {type(file_data)}")

            # Generate niche recommendations using async LLM call (optimized for speed)
            niche_analysis_prompt = NicheRecommendation(career, headline, about, currentExp, skills, topics, pastExp, processed_resume)
            messages_to_send = niche_analysis_prompt.generate_niche_prompt()

            llm_start = time.time()
            niche_analysis = await single_llm_call(
                messages=messages_to_send,
                model="gpt-4o-mini",
                max_tokens=1000,  # Compact output format needs less tokens
                temperature=0.2,  # Lower temp for faster, more consistent output
                response_format={"type": "json_object"}
            )
            print(f"[profileAnalysis] LLM call took: {time.time() - llm_start:.2f}s")

            niche_recomendation_cleaner = Clean_JSON(niche_analysis.choices[0].message.content)
            cleaned_niche_analysis = niche_recomendation_cleaner.clean_json_response()

            try:
                parsed_nicheRecom_data = json.loads(cleaned_niche_analysis)
                combined_result = {
                    "niche_recommendations": parsed_nicheRecom_data
                }
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "message": "Failed to parse niche recommendation data",
                    "error": str(e),
                    "raw_response": cleaned_niche_analysis
                }

        # Only cache if data is valid (has niche_recommendations)
        if combined_result.get("niche_recommendations"):
            await set_cached_profile(f"analysis:{profile_url.strip()}", combined_result)
            print(f"[profileAnalysis] Data cached successfully")
        else:
            print(f"[profileAnalysis] WARNING: Not caching - empty or invalid data")

        total_time = time.time() - start_time
        print(f"[profileAnalysis] Total time: {total_time:.2f}s")
        return {"success": True, "message": "Analysis completed successfully", "data": combined_result}

    except Exception as e:
        print("ERROR:", e)
        raise HTTPException(500, f"Error processing personal info: {str(e)}")


@router.post("/SelectedNiche")
async def add_selected_niche(body: SelectedNicheRequest):
    try:
        profile_url = body.profile_url
        niche = body.niche

        user_doc_ref = db.collection("users").document(profile_url).collection('personalInfo')
        docs = list(user_doc_ref.limit(1).stream())

        if not docs:
            raise HTTPException(404, "User personal info not found")

        doc_id = docs[0].id
        user_doc_ref.document(doc_id).update({
            "niche": niche
        })

        return {
            "success": True,
            "message": "Selected niche updated successfully"
        }

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(500, str(e))


@router.post("/personalInfo")
async def create_personal_info(
    url: str = Form(...),
    email: str = Form(...),
    name: str = Form(...),
    userDescription: str = Form(...),
    purpose: List[str] = Form([]),
    careerVision: str = Form(...),
    headline: str = Form(...),
    ssiScore: Optional[List[UploadFile]] = File(None),
    profileFile: Optional[List[UploadFile]] = File(None),
    resume: Optional[List[UploadFile]] = File(None),
    currentExp: str = Form(...),
    topics: List[str] = Form([]),
    skills: List[str] = Form([]),
    myValue: List[str] = Form([]),
):
    try:
        file_cvt = File_to_Base64()
        ssiScore_list = []
        if ssiScore is not None:
            for file in ssiScore:
                if hasattr(file, 'filename') and file.filename:
                    print(f"Processing file: {file}")
                    converted_file = await file_cvt.file_to_base64(file)
                    ssiScore_list.append(converted_file)

        profileFile_list = []
        if profileFile is not None:
            for file in profileFile:
                if hasattr(file, 'filename') and file.filename:
                    profileFile_list.append(await file_cvt.file_to_base64(file))

        resume_list = []
        if resume is not None:
            for file in resume:
                if hasattr(file, 'filename') and file.filename:
                    resume_list.append(await file_cvt.file_to_base64(file))

        data = {
            "email": email,
            "name": name,
            "userDescription": userDescription,
            "purpose": purpose,
            "careerVision": careerVision,
            "headline": headline,
            "ssiScoreFiles": ssiScore_list,
            "profileFileAnalytics": profileFile_list,
            "resumeFiles": resume_list,
            "currentExp": currentExp,
            "topicsFiles": topics,
            "skillsFiles": skills,
            "myValue": myValue
        }

        _, doc_ref = db.collection("users").document(url).collection('personalInfo').add(data)

        return {
            "success": True,
            "message": "Personal information saved successfully",
            "document_id": doc_ref.id
        }

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(500, str(e))


@router.post("/signin", response_model=GoogleSignInResponse)
async def google_sign_in(request: GoogleSignInRequest):
    try:
        doc_ref = (
            db.collection("users")
            .document(request.profileURL)
            .collection('personalInfo')
        )
        docs = list(doc_ref.limit(1).stream())

        user_exists = len(docs) > 0
        if user_exists:
            return GoogleSignInResponse(message="existing_user")
        else:
            return GoogleSignInResponse(message="new_user")

    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during authentication"
        )


@router.post("/AIcomments")
async def get_ai_comments(body: CommentsBody):
    post = body.post
    prompt = body.prompt if body.prompt else "Professional, positive, conversational comment"
    tone = body.tone if body.tone else "Professional, positive, conversational tone"
    persona = body.persona if body.persona else "Mid level professional with a focus on collaboration and innovation"
    language = body.language if body.language else 'Use American English with plain, conversational language. Short sentences, common vocabulary, American spelling (color, organize), friendly and easy to understand.'
    commnets_input = Comments(prompt, persona, tone, post, language)
    try:
        response = await async_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an AI that writes authentic, high-quality LinkedIn comments that sound like they were written by a real professional—not generic or promotional."},
                {
                    "role": "user",
                    "content": commnets_input.generate_prompt()
                }
            ],
            max_tokens=80,
            temperature=0.3,
        )
        comment = response.choices[0].message.content.strip()
        return {"comment": comment}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/AIposts")
def get_ai_postsContent(body: PostBody):
    userReq = body.userReq
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates engaging LinkedIn Posts."},
                {"role": "user", "content": f"""
                You are a LinkedIn content-creation assistant. You specialize in crafting polished, professional LinkedIn posts that resonate with a business audience.
                Your task is to analyze the following user's requirements and genrate high-quality Linkdin posts descriptionss based on those requirements.

                Your description must be suitable for LinkedIn, adhering to professional standards and best practices for engagement.
                It should be clear, concise, and tailored to a business audience.
                Language should be formal yet approachable, avoiding slang or overly casual expressions.

                Format:
                • The output should be structured with short paragraphs for easy readability.
                • Use bullet points or numbered lists where appropriate to enhance clarity.
                • Ensure the tone is professional, insightful, and value-driven.
                • If the user requests a specific style or format, ensure that the output aligns with those specifications. Give user's instructions high priority in your response.
                • Do NOT repeat the userReq verbatim—elevate and clarify it.
                • No hashtags unless explicitly requested.
                • No emojis unless explicitly requested.
                • Only provide the post description as output; do not include any additional commentary or explanations.
                This output will be used directly as LinkedIn post content, so it must be engaging and well-crafted. These posts are intended to foster professional connections and discussions on LinkedIn.
                It will be viewed by a diverse audience of professionals and students so maintain a tone that is inclusive and respectful.

                 Input Data (User Requirements):
                 {userReq}

                Ouptut:
                Provie the LinkedIn post descriptions based on the above user requirements.
                Write only the final post descriptions (no explanations, no titles, no quotes).
                """}
            ],
            max_tokens=1000,
            n=1,
            stop=None,
            temperature=0.7,
        )
        posts = response.choices[0].message.content.strip()
        print(posts)
        return {"posts": posts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/askAIChats")
def ask_ai_chats(body: AskAIChat):
    userMsg = body.message
    history = body.history
    profile_url = body.profile_url
    print('user message:', userMsg)
    print('conversation history:', history)
    print('profile_url:', profile_url)

    headline = ""
    currentExp = ""
    pastExp = ""
    about = ""
    topics = []
    skills = []
    career = ""
    if profile_url:
        try:
            documents = []
            doc_ref = (
                db.collection("users")
                .document(profile_url.strip())
                .collection("personalInfo")
                .stream()
            )

            for d in doc_ref:
                documents.append(d.to_dict())

            for doc in documents:
                headline = doc.get("headline", "")
                currentExp = doc.get("currentExp", "")
                pastExp = doc.get("pastExperience", "")
                about = doc.get("userDescription", "")
                career = doc.get("careerVision", "")
                topic_files = doc.get("topicsFiles", [])
                if topic_files:
                    for topic in topic_files:
                        topics.append(topic)
                skills_files = doc.get("skillsFiles", [])
                if skills_files:
                    for skill in skills_files:
                        skills.append(skill)
        except Exception as e:
            print(f"Error fetching user data: {e}")
    try:
        system_content = f"""
        Role: You are a LinkedIn brand Content Creator.
        Task: Assist users based on their request to improve their LinkedIn presence. Below is the background information of the user to help you provide better responses.

        Background Information of user:
        LinkedIn Headline: {headline}
        Current Experience: {currentExp}
        Past Experience: {pastExp}
        About: {about}
        User's topics of interest: {', '.join(topics)}
        User's skills: {', '.join(skills)}
        User's career vision: {career}

        Guidelines:
        1. Use the background information to tailor your responses to the user's professional profile and aspirations.
        2. Ensure that your responses align with LinkedIn's professional standards and best practices.
        3. Provide actionable advice that the user can implement to enhance their LinkedIn presence.
        4. Take the user background information into account while responding to the user's requests.
        5. Act as if you have user's personality, preferences, and style in mind while responding.
        """

        messages = [{"role": "system", "content": system_content}]

        for i, msg in enumerate(history):
            if i % 2 == 0:
                messages.append({"role": "user", "content": msg})
            else:
                messages.append({"role": "assistant", "content": msg})

        messages.append({"role": "user", "content": userMsg})

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=1000,
            n=1,
            stop=None,
            temperature=0.7,
        )
        aiResponse = response.choices[0].message.content.strip()
        print(aiResponse)
        return {"response": aiResponse}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/nicheRecommendations")
async def get_niche_recommendations(body: nicheRecommend):
    try:
        # Check cache first
        cache_key = f"niche_rec:{body.profile_url}:{body.niche}"
        cached_data = await get_cached_profile(cache_key)
        if cached_data:
            print(f"Cache hit for niche recommendations: {body.profile_url}")
            return {"success": True, "message": "Data retrieved from cache", "data": cached_data}

        documents = []
        doc_ref = (
            db.collection("users")
            .document(body.profile_url)
            .collection("personalInfo")
            .stream()
        )

        for d in doc_ref:
            documents.append(d.to_dict())

        for doc in documents:
            headline = doc.get("headline", "")
            currentExp = doc.get("currentExp", "")
            pastExp = doc.get("pastExperience", "")
            about = doc.get("userDescription", "")
            career = doc.get("careerVision", "")
            topic_files = doc.get("topicsFiles", [])
            topics = []
            if topic_files:
                for topic in topic_files:
                    topics.append(topic)
            skills_files = doc.get("skillsFiles", [])
            skills = []
            if skills_files:
                for skill in skills_files:
                    skills.append(skill)

        niche_analysis_prompt = NicheSpecificRecommendation(career, headline, about, currentExp, skills, topics, pastExp, body.niche)

        # Use async LLM call
        niche_analysis = await single_llm_call(
            messages=niche_analysis_prompt.generate_ssi_recommendations(),
            model="gpt-4o-mini",
            max_tokens=800
        )
        niche_recomendation_cleaner = Clean_JSON(niche_analysis.choices[0].message.content)
        cleaned_niche_analysis = niche_recomendation_cleaner.clean_json_response()
        try:
            recommendations_data = json.loads(cleaned_niche_analysis)
        except json.JSONDecodeError as e:
            print(f"Error parsing niche recommendations: {e}")
            print(f"Raw niche recommendations response: {cleaned_niche_analysis}")
            return {
                "success": False,
                "message": "Failed to parse niche recommendations",
                "error": str(e),
                "raw_niche_recommendations_response": cleaned_niche_analysis
            }

        # Cache the result
        await set_cached_profile(cache_key, recommendations_data)

        return {"success": True, "message": "Niche recommendations generated successfully", "data": recommendations_data}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(500, str(e))
