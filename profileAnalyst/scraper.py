from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import json
import time
import random
import argparse
import os
import datetime
import threading

# Load .env file (LINKEDIN_EMAIL, LINKEDIN_PASSWORD)
load_dotenv()

# Use persistent volume on Fly.io, local directory otherwise
if os.getenv("FLY_APP_NAME"):
    SESSION_FILE = "/data/linkedin_session.json"
else:
    SESSION_FILE = os.path.join(os.path.dirname(__file__), "linkedin_session.json")

# Cap concurrent browser instances to prevent OOM
# Raise or lower depending on your server's RAM (3 is safe for ~1–2GB)
_SCRAPE_SEMAPHORE = threading.Semaphore(3)

BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-infobars",
    "--disable-dev-shm-usage",
]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

VIEWPORT = {"width": 1920, "height": 1080}


def _random_delay(min_s=1.0, max_s=3.0):
    time.sleep(random.uniform(min_s, max_s))


def _scroll_to_bottom(page):
    """Smooth scroll to load all lazy-loaded content."""
    prev_height = 0
    for _ in range(20):
        page.evaluate("window.scrollBy(0, 600)")
        time.sleep(random.uniform(0.4, 0.8))
        curr_height = page.evaluate("document.body.scrollHeight")
        if curr_height == prev_height:
            break
        prev_height = curr_height
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.5)


def _click_see_more(page, selector):
    """Click a 'see more' / 'Show all' button if it exists."""
    try:
        btn = page.locator(selector).first
        if btn.is_visible(timeout=2000):
            btn.click()
            _random_delay(0.5, 1.0)
    except Exception:
        pass


# ──────────────────────────────────────────────
# Auto Login
# ──────────────────────────────────────────────

def auto_login() -> bool:
    """
    Automatically log in to LinkedIn using credentials from .env file.
    Saves a fresh session to SESSION_FILE on success.

    Returns True if login succeeded, False if LinkedIn blocked it
    (e.g. CAPTCHA, email verification challenge).

    Set in your .env file (or Fly.io secrets):
        LINKEDIN_EMAIL=you@example.com
        LINKEDIN_PASSWORD=yourpassword
    """
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")

    if not email or not password:
        raise RuntimeError(
            "LINKEDIN_EMAIL and LINKEDIN_PASSWORD must be set in your .env file "
            "or as environment variables."
        )

    print("Auto-login: starting...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=BROWSER_ARGS)
        context = browser.new_context(user_agent=USER_AGENT, viewport=VIEWPORT)
        try:
            page = context.new_page()
            page.set_default_timeout(30_000)

            page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
            _random_delay(1.5, 2.5)

            # Fill in credentials
            page.fill("#username", email)
            _random_delay(0.5, 1.0)
            page.fill("#password", password)
            _random_delay(0.5, 1.0)
            page.click('button[type="submit"]')

            page.wait_for_load_state("load")
            _random_delay(2.0, 3.5)

            current_url = page.url.lower()

            # LinkedIn is asking for CAPTCHA or email verification — can't automate this
            if any(x in current_url for x in ["/checkpoint", "/challenge", "/verify"]):
                print(
                    "Auto-login blocked: LinkedIn is asking for manual verification.\n"
                    "Run: python scraper.py --setup  to log in manually."
                )
                return False

            # Wrong password or account issue
            if any(x in current_url for x in ["/login", "/signup"]):
                print(
                    "Auto-login failed: still on login page.\n"
                    "Check LINKEDIN_EMAIL and LINKEDIN_PASSWORD in your .env file."
                )
                return False

            # Success — save session to file
            if "/feed" in current_url or "linkedin.com" in current_url:
                # Ensure the directory exists (for Fly.io /data volume)
                os.makedirs(os.path.dirname(SESSION_FILE) or ".", exist_ok=True)
                context.storage_state(path=SESSION_FILE)
                print(f"Auto-login: session saved to {SESSION_FILE}")
                return True

            print(f"Auto-login: unexpected URL after login — {page.url}")
            return False

        finally:
            context.close()
            browser.close()


# ──────────────────────────────────────────────
# Extractors
# ──────────────────────────────────────────────

def _extract_basic_info(page):
    """Extract name, headline, location, profile picture, connections, followers."""
    data = {
        "name": None,
        "headline": None,
        "location": None,
        "profile_picture_url": None,
        "connections": None,
        "followers": 0
    }

    _scroll_to_bottom(page)
    _random_delay(1.0, 2.0)

    js_data = page.evaluate("""
        () => {
            const result = {
                name: null,
                headline: null,
                location: null,
                debug: {}
            };

            const main = document.querySelector('main');
            if (!main) {
                result.debug.error = 'No main element found';
                return result;
            }

            const profileSection = main.querySelector('section');
            if (!profileSection) {
                result.debug.error = 'No section in main';
                return result;
            }

            const allText = [];
            const walker = document.createTreeWalker(
                profileSection,
                NodeFilter.SHOW_TEXT,
                null,
                false
            );

            let node;
            while (node = walker.nextNode()) {
                const text = node.textContent.trim();
                if (text.length > 0) {
                    allText.push({
                        text: text,
                        parent: node.parentElement?.tagName
                    });
                }
            }

            for (const item of allText) {
                if (item.text.length > 2 && item.text.length < 60 &&
                    !item.text.includes('Skip') &&
                    !item.text.includes('notification')) {
                    result.name = item.text;
                    break;
                }
            }

            let foundName = false;
            for (const item of allText) {
                if (item.text === result.name) {
                    foundName = true;
                    continue;
                }
                if (foundName && item.text.length > 10 && item.text.length < 300) {
                    if (!item.text.includes('Connect') &&
                        !item.text.includes('Message') &&
                        !item.text.includes('More') &&
                        !item.text.includes('followers')) {
                        result.headline = item.text;
                        break;
                    }
                }
            }

            for (const item of allText) {
                const lower = item.text.toLowerCase();
                if ((lower.includes('india') || lower.includes('united') ||
                     lower.includes('city') || lower.includes('area') ||
                     item.text.includes(',')) &&
                    item.text.length < 100) {
                    result.location = item.text;
                    break;
                }
            }

            result.connections = null;
            result.followers = 0;

            for (let i = 0; i < allText.length; i++) {
                const text = allText[i].text.toLowerCase();
                if (text === 'connections' && !result.connections) {
                    if (i > 0) {
                        const prevText = allText[i-1].text;
                        if (/^\d+\+?$/.test(prevText)) {
                            result.connections = prevText;
                        } else if (/^[\d,]+$/.test(prevText)) {
                            result.connections = parseInt(prevText.replace(/,/g, ''));
                        }
                    }
                }
                if (text === 'followers' && result.followers === 0) {
                    if (i > 0 && /^[\d,]+$/.test(allText[i-1].text)) {
                        result.followers = parseInt(allText[i-1].text.replace(/,/g, ''));
                    }
                }
            }

            if (!result.connections) {
                const fullText = document.body.innerText;
                const connMatch = fullText.match(/(\d[\d,]*\+?)\s*connections?/i);
                if (connMatch) {
                    const val = connMatch[1].replace(/,/g, '');
                    result.connections = val.includes('+') ? val : parseInt(val);
                }
            }

            if (result.followers === 0) {
                const fullText = document.body.innerText;
                const followersMatch = fullText.match(/(\d[\d,]*)\s*followers?/i);
                if (followersMatch) {
                    result.followers = parseInt(followersMatch[1].replace(/,/g, ''));
                }
            }

            return result;
        }
    """)

    data["name"] = js_data.get("name")
    data["headline"] = js_data.get("headline")
    data["location"] = js_data.get("location")
    data["connections"] = js_data.get("connections")
    data["followers"] = js_data.get("followers", 0)

    try:
        src = page.evaluate("""
            () => {
                const main = document.querySelector('main');
                if (!main) return null;

                const imgs = main.querySelectorAll('img');
                for (const img of imgs) {
                    const src = img.src || img.currentSrc;
                    if (src && src.includes('licdn.com') &&
                        (src.includes('profile-displayphoto') || src.includes('shrink_')) &&
                        !src.includes('background') &&
                        !src.includes('banner') &&
                        !src.includes('header') &&
                        !src.includes('ghost') &&
                        !src.includes('data:image')) {
                        return src;
                    }
                }

                for (const img of imgs) {
                    const src = img.src || img.currentSrc;
                    if (src && src.includes('licdn.com') &&
                        !src.includes('background') &&
                        !src.includes('banner') &&
                        !src.includes('ghost') &&
                        img.width > 50 && img.width < 500 &&
                        Math.abs(img.width - img.height) < 50) {
                        return src;
                    }
                }
                return null;
            }
        """)
        data["profile_picture_url"] = src
    except Exception:
        data["profile_picture_url"] = None

    return data


def _extract_about(page):
    """Extract the About section by finding header text."""
    try:
        about_text = page.evaluate("""
            () => {
                // Find section containing "About" header text
                const sections = document.querySelectorAll('main section');
                for (const section of sections) {
                    const text = section.innerText || '';
                    // Check if this section starts with "About" as header
                    if (text.startsWith('About') || text.includes('\\nAbout\\n')) {
                        // Get all text content, excluding the header
                        const allText = [];
                        const walker = document.createTreeWalker(
                            section,
                            NodeFilter.SHOW_TEXT,
                            null,
                            false
                        );

                        let node;
                        let foundAbout = false;
                        while (node = walker.nextNode()) {
                            const t = node.textContent.trim();
                            if (t === 'About') {
                                foundAbout = true;
                                continue;
                            }
                            if (foundAbout && t.length > 20 &&
                                !t.includes('see more') &&
                                !t.includes('see less')) {
                                allText.push(t);
                            }
                        }

                        if (allText.length > 0) {
                            return allText.join(' ');
                        }
                    }
                }
                return null;
            }
        """)
        return about_text if about_text else None
    except Exception:
        return None


def _extract_experience(page):
    """Extract all experience entries by finding header text and using TreeWalker."""
    try:
        experiences = page.evaluate("""
            () => {
                // Find section containing "Experience" header
                const sections = document.querySelectorAll('main section');
                let expSection = null;
                for (const section of sections) {
                    const text = section.innerText || '';
                    if (text.startsWith('Experience') || text.includes('\\nExperience\\n')) {
                        expSection = section;
                        break;
                    }
                }
                if (!expSection) return [];

                // Collect all text nodes from the experience section
                const allText = [];
                const walker = document.createTreeWalker(
                    expSection,
                    NodeFilter.SHOW_TEXT,
                    null,
                    false
                );

                let node;
                while (node = walker.nextNode()) {
                    const text = node.textContent.trim();
                    if (text.length > 0 && text !== 'Experience' &&
                        !text.includes('Show all') &&
                        !text.includes('see more') &&
                        !text.includes('see less')) {
                        allText.push(text);
                    }
                }

                // Parse text into experience entries
                const results = [];
                let currentEntry = null;
                const seenEntries = new Set();

                for (let i = 0; i < allText.length; i++) {
                    const text = allText[i];
                    const nextText = allText[i + 1] || '';

                    // Company pattern: contains · with employment type
                    const isCompany = text.includes('·') &&
                        (text.includes('Full-time') || text.includes('Part-time') ||
                         text.includes('Internship') || text.includes('Contract') ||
                         text.includes('Freelance') || text.includes('Self-employed'));

                    // Duration pattern
                    const isDuration = /\\d{4}/.test(text) &&
                        (text.includes(' - ') ||
                         text.toLowerCase().includes('present') ||
                         /\\d+\\s*(yr|mo|year|month)/i.test(text));

                    // Location pattern
                    const isLocation = !isCompany && !isDuration &&
                        ((text.includes(',') && text.length < 60) ||
                         (text.toLowerCase().includes('remote') && text.length < 50) ||
                         (text.toLowerCase().includes('united states') && text.length < 80) ||
                         (text.toLowerCase().includes('india') && text.length < 50));

                    // Skills pattern (skip)
                    const isSkills = text.toLowerCase().includes('skills') &&
                        (text.includes(':') || text.includes('+'));

                    // Skip UI elements
                    if (text === '·' || text === '-' || text === '•' ||
                        /^\\d+$/.test(text) || text.length < 2 || isSkills) {
                        continue;
                    }

                    if (isCompany && currentEntry && !currentEntry.company) {
                        currentEntry.company = text;
                        continue;
                    }

                    if (isDuration && currentEntry && !currentEntry.duration) {
                        currentEntry.duration = text;
                        continue;
                    }

                    if (isLocation && currentEntry && !currentEntry.location) {
                        currentEntry.location = text;
                        continue;
                    }

                    // Description: long text
                    if (text.length > 80 && !isDuration && !isCompany && currentEntry) {
                        currentEntry.description = text;
                        continue;
                    }

                    // Job title: short text not matching other patterns
                    // Next item should be company (contains employment type indicator)
                    if (text.length > 2 && text.length < 80 &&
                        !isDuration && !isLocation && !isCompany) {
                        // Check if next looks like company
                        const nextIsCompany = nextText.includes('·') &&
                            (nextText.includes('Full-time') || nextText.includes('Part-time') ||
                             nextText.includes('Internship') || nextText.includes('Contract'));

                        if (nextIsCompany) {
                            // Save previous entry
                            if (currentEntry && currentEntry.title && currentEntry.company) {
                                const key = currentEntry.title + '|' + currentEntry.company;
                                if (!seenEntries.has(key)) {
                                    seenEntries.add(key);
                                    results.push(currentEntry);
                                }
                            }

                            currentEntry = {
                                title: text,
                                company: null,
                                duration: null,
                                location: null,
                                description: null
                            };
                        }
                    }
                }

                // Save last entry
                if (currentEntry && currentEntry.title && currentEntry.company) {
                    const key = currentEntry.title + '|' + currentEntry.company;
                    if (!seenEntries.has(key)) {
                        results.push(currentEntry);
                    }
                }

                return results;
            }
        """)
        return experiences if experiences and isinstance(experiences, list) else []
    except Exception:
        return []


def _extract_education(page):
    """Extract all education entries by finding header text and using TreeWalker."""
    try:
        education = page.evaluate("""
            () => {
                // Find section containing "Education" header
                const sections = document.querySelectorAll('main section');
                let eduSection = null;
                for (const section of sections) {
                    const text = section.innerText || '';
                    if (text.startsWith('Education') || text.includes('\\nEducation\\n')) {
                        eduSection = section;
                        break;
                    }
                }
                if (!eduSection) return [];

                // Collect all text nodes from the education section
                const allText = [];
                const walker = document.createTreeWalker(
                    eduSection,
                    NodeFilter.SHOW_TEXT,
                    null,
                    false
                );

                let node;
                while (node = walker.nextNode()) {
                    const text = node.textContent.trim();
                    if (text.length > 0 && text !== 'Education' &&
                        !text.includes('Show all') &&
                        !text.includes('see more') &&
                        !text.includes('see less') &&
                        text !== '·' && text !== '-') {
                        allText.push(text);
                    }
                }

                // Parse text into education entries
                const results = [];
                let currentEntry = null;
                const seenSchools = new Set();

                for (let i = 0; i < allText.length; i++) {
                    const text = allText[i];

                    // Date pattern: contains year range
                    const isDate = /\\d{4}\\s*[-–]\\s*\\d{4}/.test(text) ||
                        /\\d{4}\\s*[-–]\\s*(Present|present)/.test(text) ||
                        /^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\\s+\\d{4}/.test(text);

                    // Skip short meaningless text
                    if (text.length < 2 || /^\\d+$/.test(text)) continue;

                    if (isDate && currentEntry) {
                        currentEntry.dates = text;
                        continue;
                    }

                    // Degree patterns - check FIRST before school
                    const looksLikeDegree = text.length > 3 && text.length < 150 &&
                        (text.includes('Bachelor') || text.includes('Master') ||
                         text.includes("Master's") || text.includes("Bachelor's") ||
                         text.includes('B.Tech') || text.includes('M.Tech') ||
                         text.includes('B.') || text.includes('M.') ||
                         text.includes('BTech') || text.includes('MTech') ||
                         text.includes('Ph.D') || text.includes('MBA') ||
                         text.includes('degree'));

                    // School names - must contain institution keyword
                    const looksLikeSchool = text.length > 5 && text.length < 150 &&
                        !looksLikeDegree &&
                        (text.toLowerCase().includes('university') ||
                         text.toLowerCase().includes('college') ||
                         text.toLowerCase().includes('institute') ||
                         text.toLowerCase().includes('school') ||
                         text.toLowerCase().includes('academy'));

                    if (looksLikeSchool) {
                        // Save previous entry if valid
                        if (currentEntry && currentEntry.school && !seenSchools.has(currentEntry.school)) {
                            seenSchools.add(currentEntry.school);
                            results.push(currentEntry);
                        }
                        currentEntry = {
                            school: text,
                            degree: null,
                            dates: null
                        };
                    } else if (looksLikeDegree) {
                        if (currentEntry) {
                            currentEntry.degree = text;
                        }
                    }
                }

                // Save last entry
                if (currentEntry && currentEntry.school && !seenSchools.has(currentEntry.school)) {
                    results.push(currentEntry);
                }

                return results;
            }
        """)
        return education if education and isinstance(education, list) else []
    except Exception:
        return []


def _extract_skills(page, profile_url):
    """Navigate to the skills detail page and extract all skills."""
    try:
        skills_url = profile_url.rstrip("/") + "/details/skills/"
        page.goto(skills_url, wait_until="domcontentloaded")
        _random_delay(1.5, 2.5)
        _scroll_to_bottom(page)

        skills = page.evaluate("""
            () => {
                const results = [];
                const seen = new Set();

                const skipTexts = new Set([
                    'all', 'industry knowledge', 'tools & technologies',
                    'interpersonal skills', 'other skills', 'skills',
                    'languages', 'certifications', 'show all', 'see more',
                    'see less', 'endorsement', 'endorsements', 'skill details',
                    'add skill', 'take skill quiz', 'load more'
                ]);

                const stopWords = [
                    'ad options', 'why am i seeing', 'more profiles for you',
                    'about', 'accessibility', 'talent solutions',
                    'community guidelines', 'careers', 'privacy',
                    'linkedin corporation', 'help center'
                ];

                const main = document.querySelector('main');
                if (!main) return [];

                const allText = [];
                const walker = document.createTreeWalker(
                    main,
                    NodeFilter.SHOW_TEXT,
                    null,
                    false
                );

                let node;
                while (node = walker.nextNode()) {
                    const text = node.textContent.trim();
                    if (text.length > 0) {
                        allText.push(text);
                    }
                }

                for (const text of allText) {
                    const lower = text.toLowerCase();

                    if (stopWords.some(sw => lower.includes(sw))) break;
                    if (seen.has(lower) || skipTexts.has(lower)) continue;
                    if (text.length < 2 || text.length > 60) continue;
                    if (/^\d+$/.test(text)) continue;
                    if (/^\d+\s*(endorsement|connection|skill)/i.test(text)) continue;
                    if (text.includes('·') || text === '-') continue;
                    if (text.includes('Show') || text.includes('Add') ||
                        text.includes('Take') || text.includes('Quiz')) continue;
                    if (text.includes('Passed') || text.includes('Assessment')) continue;
                    if (text.includes(' at ') || text.includes(' @ ')) continue;
                    if (text.includes('Connect')) continue;

                    results.push(text);
                    seen.add(lower);
                }

                return results;
            }
        """)
        return skills if skills and isinstance(skills, list) else []
    except Exception:
        return []


def _extract_certifications(page, profile_url):
    """Navigate to the certifications detail page and extract entries."""
    try:
        certs_url = profile_url.rstrip("/") + "/details/certifications/"
        page.goto(certs_url, wait_until="domcontentloaded")
        _random_delay(1.5, 2.5)
        _scroll_to_bottom(page)

        certs = page.evaluate("""
            () => {
                const results = [];
                const main = document.querySelector('main');
                if (!main) return [];

                const skipTexts = new Set([
                    'certifications', 'licenses & certifications', 'show all',
                    'see more', 'see less', 'add certification', 'credential id',
                    'show credential', 'see credential', 'skills:'
                ]);

                const stopWords = [
                    'ad options', 'why am i seeing', 'more profiles for you',
                    'about', 'accessibility', 'talent solutions',
                    'community guidelines', 'careers', 'privacy',
                    'linkedin corporation', 'help center', '· 3rd'
                ];

                const allText = [];
                const walker = document.createTreeWalker(
                    main,
                    NodeFilter.SHOW_TEXT,
                    null,
                    false
                );

                let node;
                while (node = walker.nextNode()) {
                    const text = node.textContent.trim();
                    if (text.length > 0) allText.push(text);
                }

                let currentEntry = null;
                const seenCerts = new Set();

                for (let i = 0; i < allText.length; i++) {
                    const text = allText[i];
                    const lower = text.toLowerCase();

                    if (stopWords.some(sw => lower.includes(sw))) break;
                    if (skipTexts.has(lower) || text.length < 2) continue;
                    if (text === '·' || text === '-' || /^\d+$/.test(text)) continue;
                    if (text.startsWith('Credential ID')) continue;
                    if (text.endsWith('.pdf')) continue;

                    const isDate = /^issued/i.test(text);
                    const isIssuer = (lower.includes('coursera') || lower.includes('udemy') ||
                        lower.includes('linkedin learning') || lower.includes('google') ||
                        lower.includes('microsoft') || lower.includes('aws') ||
                        lower.includes('deeplearning.ai') || lower.includes('stanford')) &&
                        !lower.includes('certificate');

                    if (isDate && currentEntry) {
                        currentEntry.date = text;
                        continue;
                    }

                    if (isIssuer && currentEntry && !currentEntry.issuing_org) {
                        currentEntry.issuing_org = text;
                        continue;
                    }

                    if (text.length > 5 && text.length < 150 && !isDate && !isIssuer) {
                        if (lower.includes('machine learning,') || lower.includes('algorithms,')) continue;

                        if (currentEntry && currentEntry.name) {
                            if (!seenCerts.has(currentEntry.name.toLowerCase())) {
                                seenCerts.add(currentEntry.name.toLowerCase());
                                results.push(currentEntry);
                            }
                        }

                        currentEntry = { name: text, issuing_org: null, date: null };
                    }
                }

                if (currentEntry && currentEntry.name) {
                    if (!seenCerts.has(currentEntry.name.toLowerCase())) {
                        results.push(currentEntry);
                    }
                }

                return results;
            }
        """)
        return certs if certs and isinstance(certs, list) else []
    except Exception:
        return []


def _extract_recent_activity(page, profile_url):
    """Navigate to the activity page and extract recent posts."""
    try:
        activity_url = profile_url.rstrip("/") + "/recent-activity/all/"
        page.goto(activity_url, wait_until="domcontentloaded")
        _random_delay(2.0, 3.0)

        # Scroll a bit to load some posts
        for _ in range(3):
            page.evaluate("window.scrollBy(0, 800)")
            time.sleep(random.uniform(0.5, 1.0))

        posts = page.evaluate("""
            () => {
                const results = [];
                const main = document.querySelector('main');
                if (!main) return [];

                // Find all feed items (posts)
                const feedItems = main.querySelectorAll('div[data-urn]');
                const count = Math.min(feedItems.length, 5);

                for (let i = 0; i < count; i++) {
                    const item = feedItems[i];
                    const post = { text: null, reactions: null, comments: null };

                    // Get post text
                    const allText = [];
                    const walker = document.createTreeWalker(
                        item,
                        NodeFilter.SHOW_TEXT,
                        null,
                        false
                    );

                    let node;
                    while (node = walker.nextNode()) {
                        const text = node.textContent.trim();
                        // Filter for actual post content
                        if (text.length > 30 && text.length < 3000 &&
                            !text.includes('Like') &&
                            !text.includes('Comment') &&
                            !text.includes('Repost') &&
                            !text.includes('Send')) {
                            allText.push(text);
                        }
                    }

                    if (allText.length > 0) {
                        post.text = allText.join(' ').substring(0, 1000);
                    }

                    // Find reaction count (number followed by reaction indicators)
                    const allNums = item.querySelectorAll('span');
                    for (const span of allNums) {
                        const t = span.textContent.trim();
                        if (/^\\d+$/.test(t) || /^\\d+,\\d+$/.test(t)) {
                            if (!post.reactions) post.reactions = t;
                            else if (!post.comments) post.comments = t;
                        }
                    }

                    if (post.text) {
                        results.push(post);
                    }
                }

                return results;
            }
        """)
        return posts if posts else []
    except Exception:
        return []


def _is_session_expired(page) -> bool:
    """Returns True if the current page indicates the session has expired."""
    page_url = page.url.lower()
    if any(x in page_url for x in ["/login", "/authwall", "/signup", "/checkpoint"]):
        return True
    try:
        h1_text = page.locator("h1").first.inner_text(timeout=3000).strip().lower()
        if h1_text in ("join linkedin", "sign in", "sign up"):
            return True
    except Exception:
        pass
    return False


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def setup_session():
    """
    Manual fallback: opens a browser for manual login.
    Use this if auto_login() fails due to CAPTCHA or verification challenges.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=BROWSER_ARGS)
        context = browser.new_context(user_agent=USER_AGENT, viewport=VIEWPORT)
        page = context.new_page()
        page.goto("https://www.linkedin.com/login")

        print("=" * 50)
        print("Log in to LinkedIn in the browser window.")
        print("Press ENTER here after you have logged in.")
        print("=" * 50)
        input()

        os.makedirs(os.path.dirname(SESSION_FILE) or ".", exist_ok=True)
        context.storage_state(path=SESSION_FILE)
        browser.close()
        print("Session saved to:", SESSION_FILE)


def scrape_profile(profile_url: str, headless: bool = True, _is_retry: bool = False) -> dict:
    """
    Scrape a LinkedIn profile and return structured data.

    - If no session exists, auto-logs in using LINKEDIN_EMAIL / LINKEDIN_PASSWORD from .env
    - If session expires mid-scrape, auto-logs in again and retries once
    - Falls back gracefully if LinkedIn blocks the auto-login (CAPTCHA etc.)

    Args:
        profile_url: Full LinkedIn profile URL (e.g. https://www.linkedin.com/in/username)
        headless: Run browser in headless mode (default True)

    Returns:
        Dict with keys: profile_url, basic_info, about, experience,
                        education, skills, certifications, recent_posts, scraped_date
    """
    profile_url = profile_url.rstrip("/")
    if not profile_url.startswith("https://"):
        profile_url = "https://" + profile_url

    # No session file — try to auto-login before doing anything else
    if not os.path.exists(SESSION_FILE):
        print("No session file found. Attempting auto-login...")
        if not auto_login():
            raise RuntimeError(
                "Auto-login failed. LinkedIn may require manual verification.\n"
                "Run: python scraper.py --setup"
            )

    result = {"profile_url": profile_url}

    with _SCRAPE_SEMAPHORE:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless, args=BROWSER_ARGS)
            context = None
            try:
                context = browser.new_context(
                    storage_state=SESSION_FILE,
                    user_agent=USER_AGENT,
                    viewport=VIEWPORT,
                )
                page = context.new_page()
                page.set_default_timeout(30_000)

                page.goto(profile_url, wait_until="domcontentloaded")
                page.wait_for_load_state("load")
                _random_delay(2.0, 3.5)

                page.evaluate("window.scrollTo(0, 500)")
                _random_delay(1.5, 2.5)
                page.evaluate("window.scrollTo(0, 0)")
                _random_delay(1.0, 2.0)

                # Session expired — try to auto-login and retry the scrape once
                if _is_session_expired(page):
                    if _is_retry:
                        # Already retried once — give up
                        raise RuntimeError(
                            "Session expired even after auto-login refresh.\n"
                            "Run: python scraper.py --setup  to log in manually."
                        )
                    print("Session expired. Attempting auto-login and retry...")
                    context.close()
                    browser.close()
                    context = None
                    if auto_login():
                        # Recurse once with _is_retry=True so we don't loop infinitely
                        return scrape_profile(profile_url, headless, _is_retry=True)
                    else:
                        raise RuntimeError(
                            "Session expired and auto-login failed.\n"
                            "Run: python scraper.py --setup  to log in manually."
                        )

                print("Extracting basic info...")
                result["basic_info"] = _extract_basic_info(page)

                print("Extracting about...")
                result["about"] = _extract_about(page)

                print("Extracting experience...")
                result["experience"] = _extract_experience(page)

                print("Extracting education...")
                result["education"] = _extract_education(page)

                print("Extracting skills...")
                result["skills"] = _extract_skills(page, profile_url)

                _random_delay(1.0, 2.0)
                print("Extracting certifications...")
                result["certifications"] = _extract_certifications(page, profile_url)

                print("Extracting recent posts...")
                result["recent_posts"] = _extract_recent_activity(page, profile_url)

                result["scraped_date"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            finally:
                if context:
                    context.close()
                browser.close()

    return result


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinkedIn Profile Scraper")
    parser.add_argument("--setup", action="store_true", help="Manual login fallback (opens browser)")
    parser.add_argument("--login", action="store_true", help="Auto-login using .env credentials")
    parser.add_argument("--url", type=str, help="LinkedIn profile URL to scrape")
    parser.add_argument("--output", type=str, help="Save output to JSON file")
    parser.add_argument("--visible", action="store_true", help="Run browser in visible mode")

    args = parser.parse_args()

    if args.setup:
        setup_session()
    elif args.login:
        success = auto_login()
        print("Login successful!" if success else "Login failed.")
    elif args.url:
        data = scrape_profile(args.url, headless=not args.visible)
        output = json.dumps(data, indent=2, ensure_ascii=False)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Saved to {args.output}")
        else:
            print(output)
    else:
        parser.print_help()