class ProfileScoringPrompt:
    def __init__(self, about, headline, certifications, experiences, skills, education, profile_picture, network_size, recent_posts):
        self.about = about
        self.headline = headline
        self.certifications = certifications
        self.experiences = experiences
        self.skills = skills
        self.education = education
        self.profile_picture = profile_picture
        self.network_size = network_size
        self.recent_posts = recent_posts

    def generate_prompt(self):
        messages = [
            {
                'role': 'system',
                'content': """LinkedIn profile scorer (100 pts). Score 8 sections with analysis + improvements.

SECTIONS (use exact names): "Visual Branding"(10), "Headline"(15), "About"(20), "Experience"(25), "Skills"(10), "Recommendations"(5), "Network"(5), "Activity"(10)

SCORING: Visual=Photo5+Banner5 | Headline=Keywords5+Value5+Length5 | About=Story7+Value7+CTA6 | Experience=Bullets10+Metrics10+Complete5 | Skills=Listed5+Endorsed5 | Recommendations=5+diverse | Network=500+=5,300-499=4,200-299=3,100-199=2,<100=1 | Activity=Posts5+Engage5

OUTPUT JSON: {total_score, section_scores:[{section_name, score, max_score, current, observations:{analysis[], improvements[]}}], quick_wins[], benchmarking:{your_score, max_possible:100, tier, percentile, industry_average:65, description}}"""
            },
            {
                'role': 'user',
                'content': [
                    {"type": "text", "text": f"""Score this profile:
HEADLINE: {self.headline}
ABOUT: {self.about[:400] if self.about else ''}
EXPERIENCE: {self.experiences}
SKILLS: {self.skills}
CONNECTIONS: {self.network_size}
POSTS: {self.recent_posts}"""}
                ]
            }
        ]

        # Add profile picture if available
        if self.profile_picture:
            pic = self.profile_picture
            if pic.startswith("http") or pic.startswith("data:image"):
                messages[1]['content'].append({
                    "type": "image_url",
                    "image_url": {"url": pic}
                })
            else:
                messages[1]['content'][0]['text'] += "\n\nNote: Profile picture not available. Score Visual Branding based on available info only."
        else:
            messages[1]['content'][0]['text'] += "\n\nNote: No profile picture. Score Profile Picture subsection as 0."

        return messages
