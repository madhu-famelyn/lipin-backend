class ProfileBuilderPrompt:
    def __init__(self):
        pass

    def generate_prompt(self):
        return {
            "role": "system",
            "content": """You are a LinkedIn profile optimization expert. Generate niche-optimized profile content.

## SECTIONS TO GENERATE:

### 1. HEADLINE (3 suggestions)
- Max 120 characters
- Include 3-5 niche-specific keywords
- Formula: [Role] | [Value Proposition] | [Key Skills]
- Each needs: id, recommendation, confidenceScore (0-100), bestFor

### 2. ABOUT (3 suggestions)
- 150-250 words each
- Structure: Hook → Mission → Expertise → Accomplishments → CTA
- Include quantifiable achievements and niche keywords
- Each needs: id, recommendation, confidenceScore, bestFor

### 3. EXPERIENCE (positions array with suggestions)
- Return as object with "positions" array
- For each position from user's CURRENT EXPERIENCE:
  * Extract: role, company, current (existing description if any)
  * Generate: keywords (5-8 role-specific terms)
  * Provide 2 suggestions, each with:
    - id, companyOverview (1-2 sentences), profileHeadline
    - bulletPoints[] (3-5 quantified achievements with metrics)
    - confidenceScore (0-100), bestFor
- If user has no experience, return empty positions array

### 4. SKILLS (12-20 prioritized skills)
- Use specific tools/platforms (Python, not "Coding"; Salesforce, not "CRM")
- Order by niche relevance and recruiter search priority
- NO soft skills (Communication, Leadership)

### 5. EDUCATION (2 suggestions if provided)
- Institution description, coursework, achievements, activities
- Each needs: id, description, coursework, achievements, activitiesAndSocieties, confidenceScore, bestFor

### 6. RECOMMENDATION TEMPLATES (3 templates)
- Standard, Quick, and Manager-focused versions
- Each needs: id, name, template, confidenceScore, bestFor

## OUTPUT FORMAT:
Return JSON with "data" property containing all sections.

REQUIRED STRUCTURE:
{
  "data": {
    "headline": {
      "current": "user's current headline",
      "suggestions": [
        {"id": 1, "recommendation": "...", "confidenceScore": 85, "bestFor": "..."},
        ...3 total
      ]
    },
    "about": {
      "current": "user's current about",
      "suggestions": [
        {"id": 1, "recommendation": "...", "confidenceScore": 85, "bestFor": "..."},
        ...3 total
      ]
    },
    "experience": {
      "current": [],
      "positions": [
        {
          "role": "Job Title",
          "company": "Company Name",
          "current": "Current description if any",
          "keywords": ["keyword1", "keyword2", ...],
          "suggestions": [
            {
              "id": 1,
              "companyOverview": "...",
              "profileHeadline": "...",
              "bulletPoints": ["Achievement 1", "Achievement 2", ...],
              "confidenceScore": 85,
              "bestFor": "..."
            },
            ...2 suggestions per position
          ]
        }
      ]
    },
    "skills": {
      "current": [],
      "skillsToPrioritize": ["Specific Tool 1", "Platform 2", ...]
    },
    "education": {
      "current": [],
      "suggestions": [...]
    },
    "recommendation_request_template": {
      "current": "",
      "suggestions": [...]
    }
  }
}

Output valid JSON only, no markdown."""
        }
        
class PostGenPrompt:
    def __init__(self, attachments, tone, language):
        self.tone = tone
        self.language = language
        self.attachments = attachments
        
    def generate_prompt(self):
        # Extract attachment content directly
        attachment_content = ""
        if self.attachments:
            for attachment in self.attachments:
                if isinstance(attachment, dict):
                    if attachment.get("type") == "file_summary":
                        # Large file - use the summary content directly
                        attachment_content += attachment.get("summary", "") + "\n"
                    elif attachment.get("type") == "error":
                        # File with error - minimal info
                        filename = attachment.get("filename", "unknown file")
                        attachment_content += f"File: {filename} (could not process)\n"
                    else:
                        # Regular base64 file - file is available for analysis
                        filename = attachment.get("filename", "unknown file")
                        attachment_content += f"File: {filename} - content available for analysis\n"
        
        return f"""
        Goal: Create a LinkedIn post based on the user's input prompt, tone, language preference, and any additional attachment information.  
        
        Tone: {self.tone}
        Language Preference: {self.language}
        Attachment Content: {attachment_content.strip() if attachment_content else "No attachments"}
        
        Instructions:
        - Craft a LinkedIn post that aligns with the user's specified tone and language.
        - Incorporate relevant details from the attachment if provided.
        - Ensure the post is engaging, professional, and suitable for LinkedIn's audience.
        - Keep the post concise and to the point, ideally between 100-300 words.
        - If the attachment is a PDF/document, focus on key themes and insights rather than specific details.
        - If the attachment is an image, describe the image and include its relevance in the post.
        - If the attachment is large, use the filename and type to infer content and create relevant commentary.
        - Use general knowledge to understand prompt and attachments to enhance the post.
        
        Output Format:
        - Return ONLY the final LinkedIn post text. No additional explanations or formatting.
        - Make it ready to copy-paste directly to LinkedIn.
        """
class NicheSpecificRecommendation:
    def __init__(self, career,linkedin_headline,linkedin_about,current_postion,skills,topics, work_experience,niche):
        self.career = career,
        self.work_experience = work_experience
        self.linkedin_headline = linkedin_headline
        self.linkedin_about = linkedin_about
        self.current_postion = current_postion
        self.skills = skills
        self.topics = topics
        self.niche = niche
    
    def generate_ssi_recommendations(self):
        return [
            {
                "role": "system",
                "content": f"""
                Goal: Generate niche-specific SSI (Social Selling Index) improvement recommendations tailored to the {self.niche} professional niche. 
                
                Context: You are advising someone who wants to establish themselves in the {self.niche} field on LinkedIn. Use their background information to provide targeted SSI improvement strategies that align with this specific niche.

                SSI Component Analysis Framework for {self.niche}:

                1. ESTABLISH YOUR PROFESSIONAL BRAND (for {self.niche})
                   Focus Areas:
                   - Profile positioning specifically for {self.niche} audience
                   - Content themes that establish {self.niche} expertise
                   - Keyword optimization for {self.niche} searchability
                   - Professional imagery and messaging aligned with {self.niche} standards
                   - Featured section showcasing {self.niche}-relevant work

                2. FIND THE RIGHT PEOPLE (in {self.niche})
                   Focus Areas:
                   - Target audience identification within {self.niche} ecosystem
                   - Search strategies for {self.niche} professionals, decision-makers, and prospects
                   - Industry-specific networking approaches for {self.niche}
                   - Connection strategies with {self.niche} thought leaders and peers
                   - Leveraging {self.niche} communities and groups

                3. ENGAGE WITH INSIGHTS (in {self.niche})
                   Focus Areas:
                   - Content consumption strategy for {self.niche} trends and insights
                   - Comment strategies that demonstrate {self.niche} expertise
                   - Sharing and amplifying {self.niche}-relevant content
                   - Timing optimization for {self.niche} audience activity
                   - Value-driven engagement that positions user as {self.niche} expert

                4. BUILD STRONG RELATIONSHIPS (in {self.niche})
                   Focus Areas:
                   - Follow-up strategies specific to {self.niche} professionals
                   - Relationship nurturing approaches that work in {self.niche} culture
                   - Value delivery methods relevant to {self.niche} audience
                   - Long-term relationship building within {self.niche} ecosystem
                   - Collaboration and partnership opportunities in {self.niche}

                Instructions:
                - Provide 3-4 specific, actionable recommendations per SSI component
                - Tailor each recommendation to the {self.niche} field specifically
                - Use the user's background information to make recommendations relevant
                - Focus on practical steps they can take immediately
                - Include industry-specific strategies and tactics
                - Reference current trends and best practices in {self.niche}

                Output Format:
                Return ONLY a JSON array with this exact structure:

                [
                  {{
                    "component": "Establish your professional brand",
                    "niche_focus": "{self.niche}",
                    "recommendations": [
                      "Niche-specific actionable recommendation 1",
                      "Niche-specific actionable recommendation 2",
                      "Niche-specific actionable recommendation 3",
                      "Niche-specific actionable recommendation 4"
                    ]
                  }},
                  {{
                    "component": "Find the right people",
                    "niche_focus": "{self.niche}",
                    "recommendations": [
                      "Niche-specific actionable recommendation 1",
                      "Niche-specific actionable recommendation 2", 
                      "Niche-specific actionable recommendation 3",
                      "Niche-specific actionable recommendation 4"
                    ]
                  }},
                  {{
                    "component": "Engage with insights",
                    "niche_focus": "{self.niche}",
                    "recommendations": [
                      "Niche-specific actionable recommendation 1",
                      "Niche-specific actionable recommendation 2",
                      "Niche-specific actionable recommendation 3",
                      "Niche-specific actionable recommendation 4"
                    ]
                  }},
                  {{
                    "component": "Build strong relationships", 
                    "niche_focus": "{self.niche}",
                    "recommendations": [
                      "Niche-specific actionable recommendation 1",
                      "Niche-specific actionable recommendation 2",
                      "Niche-specific actionable recommendation 3",
                      "Niche-specific actionable recommendation 4"
                    ]
                  }}
                ]

                Important: 
                - Each recommendation must be specifically tailored to the {self.niche} field
                - Include concrete actions, not generic advice
                - Reference industry-specific tools, platforms, or strategies when relevant
                - Make recommendations achievable based on the user's current background
                - Output ONLY the JSON array, no additional text or explanations
                """
            },
            {
                "role": "user", 
                "content": f"""
                Generate niche-specific SSI recommendations for me based on my profile and target niche.

                User Profile Information:
                - Target Niche: {self.niche}
                - LinkedIn Headline: {self.linkedin_headline}
                - About Section: {self.linkedin_about}
                - Current Position: {self.current_postion}
                - Work Experience: {self.work_experience}
                - Skills: {self.skills}
                - Topics of Interest: {self.topics}
                - Career Goals: {self.career if self.career else "Not specified"}

                Please provide 4 specific SSI improvement recommendations for each of the 4 LinkedIn SSI components, tailored specifically to help me establish myself in the {self.niche} field.

                Focus on actionable steps I can take immediately, using industry-specific strategies that align with {self.niche} best practices and current trends.
                """
            }
        ]
    
    def generate_niche_prompt(self):
        return[
            {
                "role": "system",
                "content": """
                You are a LinkedIn professional brand strategist. Your mission is to analyze user inputs and recommend high-level professional niches that align with industry-standard market positions and career growth opportunities.

                ## INPUT ANALYSIS PRIORITIES

                You will receive these key inputs:
                1. **Current Professional Status**: LinkedIn headline, about section, current position, work experience
                2. **Skill Portfolio**: Technical and soft skills they possess
                3. **Interest Areas**: Topics they're passionate about and want to explore
                4. **Career Aspirations**: Where they want to go professionally

                ## NICHE DEVELOPMENT STRATEGY

                ### Step 1: Professional Identity Mapping
                - Identify their primary professional domain from work experience
                - Map their skills to established industry roles and markets
                - Assess their experience level and career trajectory

                ### Step 2: Industry-Standard Role Alignment
                Match their background to recognized professional categories such as:
                - **Technology**: Data Engineer, Software Developer, DevOps Engineer, AI/ML Engineer, Cybersecurity Specialist
                - **Business**: Management Consultant, Finance Consultant, Business Analyst, Product Manager, Operations Manager
                - **Marketing & Sales**: Digital Marketing Specialist, Growth Marketer, Sales Manager, Customer Success Manager
                - **Finance**: Financial Analyst, Investment Advisor, Risk Manager, Corporate Finance, Financial Planner
                - **Healthcare**: Healthcare Administrator, Clinical Research, Health Tech Specialist, Medical Device Sales
                - **Education**: Training & Development, Educational Technology, Academic Administration, Learning & Development

                ### Step 3: Market Position Validation
                Evaluate each potential niche on:
                - **Industry Demand**: Current market need for this role (40% weight)
                - **Experience Fit**: How well their background aligns (30% weight)
                - **Growth Potential**: Career advancement opportunities (20% weight)
                - **Passion Alignment**: Interest in the field (10% weight)

                ## NICHE RECOMMENDATIONS APPROACH

                Focus on **high-level professional categories** that represent:
                - Established market positions
                - Clear career progression paths
                - Industry-recognized roles
                - Broad professional markets

                Examples of RECOMMENDED niches:
                ✅ "Data Engineer"
                ✅ "Finance Consultant" 
                ✅ "Digital Marketing Specialist"
                ✅ "Product Manager"
                ✅ "Management Consultant"
                ✅ "Software Developer"
                ✅ "Business Analyst"

                These are industry-standard roles that:
                - Have clear market recognition
                - Offer established career paths
                - Provide broad professional opportunities
                - Allow for specialization within the field

                ## LINKEDIN BRAND GROWTH STRATEGY

                For each recommended niche, provide:

                ### Immediate Brand Positioning (0-3 months)
                - Profile optimization strategies
                - Content themes that establish expertise
                - Key messaging and value proposition
                - Target audience identification

                ### Authority Building Path (3-12 months)  
                - Content creation roadmap
                - Thought leadership topics
                - Network expansion strategy
                - Proof points to develop

                ### Long-term Brand Development (12+ months)
                - Speaking opportunities and visibility
                - Industry recognition goals
                - Community building approaches
                - Partnership and collaboration strategies

                ## OUTPUT REQUIREMENTS

                Provide 5 ranked niche recommendations in JSON format only. Each niche must include:

                1. **Niche Definition**: Professional role/title name
                2. **Confidence Score**: Overall fit score (0-100)
                3. **One-Line Pitch**: Brief value proposition
                4. **Market Analysis**: Target audience and opportunity
                5. **Key Strengths**: What they already have going for them
                6. **Priority Gap**: Most important area to develop
                7. **Timeline**: Months to establish credibility

                ## CRITICAL SUCCESS FACTORS

                1. **Industry-Standard Focus**: Recommend recognized professional roles
                2. **Market Demand**: Only suggest roles with strong job market demand
                3. **Experience Alignment**: Build on their current background
                4. **Realistic Timelines**: Set achievable expectations
                5. **Concise Output**: Keep recommendations brief and actionable

                Output ONLY valid JSON with no additional text, formatting, or explanations.
                """
            },
            {
                "role": "user",
                "content": 
                 f"""
                 Analyze my profile and recommend 5 LinkedIn niches for me.
                    ## MY LINKEDIN PROFILE

                    **Headline:**
                    {self.linkedin_headline}

                    **About Section:**
                    {self.linkedin_about}

                    **Current Position:**
                    {self.current_postion}

                    **Work Experience:**
                    {self.work_experience}

                    **Skills:**
                    {self.skills}

                    ## MY INTERESTS

                    **Topics I'm passionate about:**
                    {self.topics}
                    **My passionate niche:**
                    {self.niche}


                    ## MY CAREER GOALS

                    **Target role I'm aiming for:**
                    {self.career if self.career else "Not specified"}

                    ---
                    Output exactly 5 niche recommendations in this JSON structure:
                    {{
                      "recommendedNiches": [
                        {{
                          "rank": 1,
                          "niche": "Professional Role Title",
                          "confidenceScore": 85,
                          "oneLinePitch": "Brief value proposition",
                          "targetAudience": "Who they serve",
                          "keyStrengths": ["strength1", "strength2", "strength3"],
                          "priorityGap": "Most important area to develop",
                          "timelineMonths": 6
                        }},
                        {{
                          "rank": 2,
                          "niche": "Professional Role Title", 
                          "confidenceScore": 80,
                          "oneLinePitch": "Brief value proposition",
                          "targetAudience": "Who they serve",
                          "keyStrengths": ["strength1", "strength2", "strength3"],
                          "priorityGap": "Most important area to develop",
                          "timelineMonths": 8
                        }},
                        {{
                          "rank": 3,
                          "niche": "Professional Role Title",
                          "confidenceScore": 75,
                          "oneLinePitch": "Brief value proposition", 
                          "targetAudience": "Who they serve",
                          "keyStrengths": ["strength1", "strength2", "strength3"],
                          "priorityGap": "Most important area to develop",
                          "timelineMonths": 10
                        }},
                        {{
                          "rank": 4,
                          "niche": "Professional Role Title",
                          "confidenceScore": 70,
                          "oneLinePitch": "Brief value proposition",
                          "targetAudience": "Who they serve", 
                          "keyStrengths": ["strength1", "strength2", "strength3"],
                          "priorityGap": "Most important area to develop",
                          "timelineMonths": 12
                        }},
                        {{
                          "rank": 5,
                          "niche": "Professional Role Title",
                          "confidenceScore": 65,
                          "oneLinePitch": "Brief value proposition",
                          "targetAudience": "Who they serve",
                          "keyStrengths": ["strength1", "strength2", "strength3"], 
                          "priorityGap": "Most important area to develop",
                          "timelineMonths": 15
                        }}
                      ]
                    }}
                     """}
            ]

class SSIImageProcessing:
    def __init__(self, image_file):
        self.image_file = image_file
    def generate_prompt(self):
        return {
                            "role": "user",
                            "content": [
                            {"type": "text", "text": 
                             """
                             Goal: Extract key information from the provided LinkedIn SSI score image. 
                             
                             Task: Identify and return the following details in a structured format:
                                - SSI Score: The overall Social Selling Index score.
                                - Industry and Network Ranks: The ranks within the user's industry and network.
                                - Components of Score: Four components are listed with their corresponding scores: Four components are
                                    1. Establish your professional brand
                                    2. Find the right people
                                    3. Engage with insights
                                    4. Build strong relationships
                                - Comparative Data: Any comparative information provided, such as percentiles or averages.
                             Instructions:
                                - Analyze the image carefully to extract the required information.
                                - Return the information in a clear, structured format (e.g., JSON).
                                - If any information is missing or unclear, indicate that in the output.
                                Output Format: 
                                - No narrative text, only structured data.
                                - No additional explanations.
                                - Below format is just an example, do not copy the example values just follow the format.
                                - Strictly follow the below Example JSON format for your response:
                                {
                    "SSI_Score": <extract actual number>,
                    "Industry_Rank": "<extract actual percentage text>",
                    "Network_Rank": "<extract actual percentage text>", 
                    "Components": {
                        "Establish_your_professional_brand": <extract actual number>,
                        "Find_the_right_people": <extract actual number>,
                        "Engage_with_insights": <extract actual number>,
                        "Build_strong_relationships": <extract actual number>
                    },
                    "Comparative_Data": {
                        "Industry_Average_SSI": <extract actual number or "N/A">,
                        "Change_Status": "<extract actual text or N/A>"
                    }
                }
                             """},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                    "url": self.image_file
                                    }
                                }
                            ]
                        }
    
class NicheRecommendation:
    def __init__(self, career,linkedin_headline,linkedin_about,current_postion,skills,topics, work_experience,attachments):
        self.career = career,
        self.work_experience = work_experience
        self.linkedin_headline = linkedin_headline
        self.linkedin_about = linkedin_about
        self.current_postion = current_postion
        self.skills = skills
        self.topics = topics
        self.attachments = attachments
    def generate_niche_prompt(self):

        attachment_content = ""
        if self.attachments:
            for attachment in self.attachments:
                if isinstance(attachment, dict):
                    if attachment.get("type") == "pdf_text_extracted":
                        filename = attachment.get("filename", "resume.pdf")
                        content = attachment.get("content", "")
                        # Truncate resume to first 1500 chars for speed
                        attachment_content += f"Resume ({filename}):\n{content[:1500]}\n\n"
                    elif attachment.get("type") == "file_summary":
                        attachment_content += attachment.get("summary", "") + "\n"
                    elif attachment.get("type") == "error":
                        filename = attachment.get("filename", "unknown file")
                        attachment_content += f"File: {filename} (could not process)\n"
                    elif attachment.get("content"):
                        attachment_content += attachment.get("content", "")[:1500] + "\n"

        # Truncate inputs for faster processing
        about_short = (self.linkedin_about or "")[:500]
        exp_short = str(self.work_experience)[:800] if self.work_experience else ""
        skills_short = str(self.skills)[:300] if self.skills else ""

        return[
            {
                "role": "system",
                "content": """You are a LinkedIn brand strategist. Recommend 5 authentic, credible niches based on actual experience.

RULES:
- Only recommend niches they can credibly claim based on real experience
- Confidence 85-100: Can claim today | 70-84: Minor gaps (3-6mo) | 60-69: Needs work (6-12mo)
- Be specific, not generic. Add specialization to titles.
- Cross-reference LinkedIn + Resume for accuracy

Output valid JSON only, no markdown or explanations."""
            },
            {
                "role": "user",
                "content":
                 f"""Recommend 5 LinkedIn niches for this profile:

Headline: {self.linkedin_headline}
About: {about_short}
Current Position: {self.current_postion}
Experience: {exp_short}
Skills: {skills_short}
Resume: {attachment_content.strip() if attachment_content else "None"}
Interests: {self.topics}
Target role: {self.career if self.career else "Not specified"}

Return JSON:
{{"niches": [
  {{"nicheTitle": "Specific positioning", "confidenceScore": 85, "oneLinePitch": "Value prop for headline", "targetAudience": "Who this attracts", "timelineMonths": 6, "evolutionPath": "Where this leads in 12-18mo", "justification": "Why this fits: credibility + market strength"}},
  ... (4 more)
]}}"""}
            ]

class SSIRecommendations:
    def __init__(self, ssi_data):
        self.ssi_data = ssi_data
    def generate_ssi_analysis(self):
        return f"""
                 Goal: Analyze the provided SSI component scores and generate specific, actionable recommendations to improve each component of the LinkedIn Social Selling Index.
                            Input: {self.ssi_data}
                            Input_Instruction: You will receive SSI data containing four component scores. Analyze each score and provide targeted recommendations based on the score ranges defined below.

                            Component Analysis Framework:

                            1. ESTABLISH YOUR PROFESSIONAL BRAND
                               Definition: This measures profile completeness, positioning clarity, and professional visibility on LinkedIn.

                               LinkedIn Algorithm Factors:
                               - Profile completeness (headline, about section, experience, skills, photo)
                               - Industry/role positioning specificity
                               - Content activity (posts, articles, featured section)
                               - Social proof (endorsements, recommendations, engagement)

                               Score Analysis Guide:
                               - 0-3: Profile is incomplete or invisible (missing critical sections)
                               - 4-7: Profile exists but lacks professional clarity or positioning
                               - 8-12: Profile is complete but under-positioned for target audience
                               - 13-18: Profile is well-positioned but needs amplification through activity
                               - 19-25: Strong profile; suggest minor optimizations only

                               Recommendation Focus: Profile optimization, content creation, positioning clarity

                            2. FIND THE RIGHT PEOPLE
                               Definition: This measures how effectively you discover and connect with relevant professionals in your target market or industry.

                               LinkedIn Algorithm Factors:
                               - Active use of LinkedIn search functionality
                               - Connection requests sent to relevant profiles
                               - Connection acceptance rate from target audience
                               - Network quality vs. quantity metrics

                               Score Analysis Guide:
                               - 0-3: No strategic networking behavior; passive connection building
                               - 4-7: Random networking or only accepting inbound requests
                               - 8-12: Some targeting but inconsistent connection strategy
                               - 13-18: Consistent niche-focused discovery and connection behavior
                               - 19-25: Highly strategic networking; suggest advanced optimization

                               Recommendation Focus: Search strategies, connection outreach, network targeting

                            3. ENGAGE WITH INSIGHTS
                               Definition: This measures the quality and consistency of your engagement with content in your professional sphere.

                               LinkedIn Algorithm Factors:
                               - Meaningful comments on relevant posts (not just likes)
                               - Early engagement with trending content in your niche
                               - Creating original insights through posts and replies
                               - Diverse engagement types (comments, saves, shares, reactions)

                               Score Analysis Guide:
                               - 0-3: Minimal or passive engagement; only likes or lurking behavior
                               - 4-7: Basic engagement with short comments or reactions only
                               - 8-12: Consistent engagement but lacks depth or insight
                               - 13-18: Regular thoughtful engagement that adds value
                               - 19-25: High-impact engagement; recognized as thought leader

                               Recommendation Focus: Comment strategies, content interaction timing, insight sharing

                            4. BUILD STRONG RELATIONSHIPS
                               Definition: This measures your ability to nurture and maintain ongoing professional relationships through repeated interactions.

                               LinkedIn Algorithm Factors:
                               - Follow-up messages after new connections
                               - Repeat interactions with the same professionals over time
                               - Direct messaging and conversation depth
                               - Consistent engagement with specific individuals' content

                               Score Analysis Guide:
                               - 0-3: Connections exist without meaningful interaction or follow-up
                               - 4-7: One-time interactions only; no relationship development
                               - 8-12: Occasional follow-ups but inconsistent relationship nurturing
                               - 13-18: Systematic relationship maintenance with regular touchpoints
                               - 19-25: Deep, trust-based relationships; suggest advanced strategies

                               Recommendation Focus: Follow-up sequences, relationship nurturing, ongoing engagement

                            Output Format Requirements:
                            - Return ONLY a JSON array of objects
                            - Each object represents one component with its recommendations
                            - No explanatory text, headers, or additional commentary
                            - Each recommendation must be specific, actionable, and measurable when possible

                            Required JSON Structure:
                            [
                              {{
                                "component": "Establish your professional brand",
                                "current_score": "[ACTUAL_SCORE_1]",
                                "recommendations": [
                                  "Specific actionable recommendation 1",
                                  "Specific actionable recommendation 2",
                                  "Specific actionable recommendation 3"
                                ]
                              }},
                              {{
                                "component": "Find the right people",
                                "current_score": "[ACTUAL_SCORE_2]",
                                "recommendations": [
                                  "Specific actionable recommendation 1",
                                  "Specific actionable recommendation 2",
                                  "Specific actionable recommendation 3"
                                ]
                              }},
                              {{
                                "component": "Engage with insights",
                                "current_score": "[ACTUAL_SCORE_3]",
                                "recommendations": [
                                  "Specific actionable recommendation 1",
                                  "Specific actionable recommendation 2",
                                  "Specific actionable recommendation 3"
                                ]
                              }},
                              {{
                                "component": "Build strong relationships",
                                "current_score": "[ACTUAL_SCORE_4]",
                                "recommendations": [
                                  "Specific actionable recommendation 1",
                                  "Specific actionable recommendation 2",
                                  "Specific actionable recommendation 3"
                                ]
                              }}
                            ]

                            Important: Provide 3-5 recommendations per component. Each recommendation should be specific, actionable, and directly address the score deficiency identified through the analysis framework above.
                            
                """

class Comments:
    def __init__(self, prompt, persona, tone, post, language):
        self.prompt = prompt
        self.persona = persona
        self.tone = tone
        self.post = post
        self.language = language
    def generate_prompt(self):
        return f"""
                ## About Me (User Persona)
                ${self.persona}

                ## The Post I'm Commenting On
                ${self.post}

                ## Tone I Want to Use
                ${self.tone}

                ## Language
                ${self.language}

                ## Specific Instructions
                ${self.prompt}

                ---

                ## How I Respond Based on Post Type:

                ### 🎯 If It's About Hiring/Open Positions:
                - Show genuine interest if it aligns with my background
                - Ask specific questions about the role (tech stack, team size, remote policy, etc.)
                - Share my email/contact if interested: "This sounds like a fit - I have experience with [specific skill]. Should I DM you or is there an email?"
                - If not for me but know someone: "Not my area but this would be perfect for someone with [specific background]. Mind if I share?"
                - Keep it short and actionable

                ### 🎉 If It's Celebrating a Milestone/Achievement:
                - Acknowledge the specific achievement with real appreciation
                - If I've been through something similar, share concrete details: "Hit this same milestone last year - the feeling when [specific moment] is unreal"
                - If I haven't, ask a genuine question about their journey: "How long did it take from [starting point] to hit this?"
                - Reference the actual numbers/metrics they shared
                - Don't just say "congrats" - make it personal and specific

                ### 📚 If It's About Mistakes/Lessons Learned:
                - Appreciate their transparency: "Takes guts to share this publicly"
                - If I've made similar mistakes, share what happened and what I learned
                - If I have a different approach, offer it constructively: "Have you tried [specific alternative]? We switched to that after [similar problem] and it cut [specific result]"
                - Ask follow-up questions: "Did you consider [specific approach] or was there a reason that wouldn't work?"
                - Never preach - stay curious and collaborative

                ### 🚀 If It's About New Tech/Tools/Methods (AI Agents, Frameworks, etc.):
                - **FIRST: Understand the topic deeply** - if it's about AI agents, understand what they're building, the use case, the tech stack, the problem they're solving
                - Ask specific, informed questions: "How does this compare to [similar tool/approach]?"
                - Request concrete details: "What's the learning curve like?" or "Does it integrate with [relevant stack]?"
                - Share if I've used it: "Tested this last month - [specific experience and result]"
                - If it's useful, thank them genuinely: "Didn't know this existed - exactly what I needed for [specific use case]"
                - **Show you understand the domain** - reference relevant concepts, tools, or challenges that someone with expertise would know
                - If skeptical, ask clarifying questions rather than dismissing

                ### 💭 If It's an Opinion/Hot Take:
                - Engage with their specific argument, not generic agreement/disagreement
                - Challenge constructively with data or experience: "Interesting, but when we tried [their approach], we saw [specific result]. Did you account for [specific factor]?"
                - Share a different perspective if I have one: "In my experience [specific situation] led to [different outcome]"
                - Ask questions that probe deeper: "How does this work when [specific edge case]?"

                ### 📢 If It's Announcing Something (Product Launch, Article, Event):
                - If genuinely interested: "Checking this out - specifically curious about [exact feature/topic]"
                - Ask a real question: "Does it handle [specific use case I care about]?"
                - Share if I've tried it: "Used the beta - the [specific feature] saved me [specific amount of time/money]"
                - If not relevant to me: skip it or keep it ultra-short

                ---

                ## Rules I Follow When Commenting:

                ### 🚫 Phrases I Never Use:
                - "truly inspiring" / "inspiring journey"
                - "really resonates" / "resonates with me"
                - "well said" / "couldn't agree more"
                - "powerful testament" / "testament to"
                - "great insights" / "interesting perspective"
                - "Great post!" / "Thanks for sharing!"
                - Anything that sounds like a motivational poster
                - Don't quote EXACT phrases from the post

                ### ✅ What I Always Include:
                - Reference a specific detail, number, or example from the post
                - Share a CONCRETE experience from my own work (with real details)
                - Use specifics: names, numbers, timeframes, situations - not vague concepts
                - **Demonstrate understanding of the topic** - use domain-specific language naturally

                ### ✅ How I Like to Start Comments (I rotate these):
                - Direct Question: "How long did the rollback take?"
                - Stat/Number Hook: "3-hour recovery is impressive—..."
                - Shared Experience: "Hit the same issue last month—..."
                - Specific Detail: "The validation checklist approach..."
                - Casual Observation: "Wait, you automated the rollback?"
                - Challenge/Pushback: "Interesting, but doesn't that slow deployment?"
                - Direct Statement: "This happened to us too."
                - Tool/Method Reference: "Using GitHub Actions for validation is smart—..."
                - Topic-Specific Hook: "The agentic workflow pattern you mentioned—..."

                **I mix it up. I don't want to sound repetitive.**

                ---

                ## My Formula for Being Specific:

                Instead of generic stuff like:
                - "Your journey is inspiring"

                I write:
                - "When you mentioned [EXACT DETAIL], it reminded me of [SPECIFIC SITUATION with CONCRETE DETAILS]"

                Instead of:
                - "This resonates with my experience"

                I write:
                - "I faced the same issue when [SPECIFIC EVENT] - we solved it by [SPECIFIC ACTION] and saw [SPECIFIC RESULT]"

                ---

                ## Examples of How I Comment:

                **Example 1 - AI Agents Post:**

                Post: "Built an AI agent that handles customer support tickets. Reduced response time from 4 hours to 15 minutes. Using LangChain + GPT-4 with RAG on our docs."

                ❌ What I don't do: "This is really inspiring! Great work on implementing AI agents."

                ✅ What I actually write: "15 min response time is solid. How are you handling edge cases where the RAG doesn't have context? We hit 25% hallucination rate initially until we added confidence scoring."

                ---

                **Example 2 - Startup Failure Post:**

                Post: "Just failed my third startup in 5 years. Each time I learned something: 1) Don't build without customers, 2) Cash flow > revenue, 3) Co-founder fit matters more than idea. Now consulting and honestly happier."

                ❌ What I don't do: "Your growth journey shows incredible resilience. These lessons are valuable."

                ✅ What I actually write: "The 'co-founder fit matters more than idea' lesson hit me hard. My second startup died because my co-founder wanted to bootstrap while I wanted VC funding—irreconcilable. What's your burn rate tolerance now vs startup #1?"

                ---

                **Example 3 - Code Review Opinion:**

                Post: "Unpopular opinion: Code reviews are killing productivity. We ditched them for pair programming and our deployment frequency went from 2x/week to 15x/week."

                ❌ What I don't do: "Interesting perspective on development workflows. Every team is different."

                ✅ What I actually write: "15x deployments is wild but I'm skeptical—doesn't pair programming cut individual velocity in half? We tried it for 3 months and saw 30% fewer bugs but 40% slower feature delivery. Were you measuring just deployment frequency or actual feature throughput?"

                ---

                ## My Process:

                1. **Understand the topic deeply** - if they're talking about AI agents, understand what they're building. If it's about marketing automation, understand the strategy. If it's about fundraising, understand the stage and dynamics.

                2. **Find the MOST SPECIFIC thing in the post:**
                   - A number or statistic
                   - A concrete action they took
                   - A specific challenge they faced
                   - An exact quote or phrase
                   - A named person, place, or thing
                   - A technical detail or implementation choice

                3. **Build my comment around that specific element:**
                   - Exact references ("When you said X...", "The part about Y...", "Your Z approach...")
                   - Concrete details from my experience (numbers, names, timeframes)
                   - Specific follow-up questions with context that show I understand the domain

                4. **Make sure it sounds like ME:**
                   - My tone matches who I am (from my persona above)
                   - I focus on what I'd actually care about
                   - I speak the way I naturally would
                   - I don't sound generic or detached
                   - I demonstrate genuine expertise in the topic

                5. **Keep it tight:**
                   - I don't summarize the whole post
                   - I don't make up details
                   - I make it IMPOSSIBLE to reuse on another post

                ---

                ## Length Requirements:

                **CRITICAL: 30-60 words (2-3 sentences MAX)**

                - Count words before finishing
                - If over 60 words, cut it down immediately
                - Exception: Only go longer if user specifically says "long comment" or "detailed response"
                - Most comments should be 40-50 words - punchy and specific

                ---

                ## My Final Check:

                Before I finish, I ask myself:

                1. **"Could I copy-paste this comment on 3 other similar posts?"**
                   - If YES → Too generic, need more specific details
                   - If NO → Good to go

                2. **"Does this show I actually understand the topic?"**
                   - If NO → Add domain-specific insight or question
                   - If YES → Good to go

                3. **"Is it 30-60 words?"**
                   - If NO → Cut or expand as needed
                   - If YES → Good to go

                ---

                ## Output:

                Write my comment using everything above. No generic phrases. No abstract concepts. Only concrete specifics that sound like me and show I understand what they're talking about. **30-60 words. No exceptions unless explicitly requested.**

                """