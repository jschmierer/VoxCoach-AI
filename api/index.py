import os
import random
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from groq import Groq
from supabase import create_client, Client

# Pull local tracking keys and configurations
load_dotenv()

import os

# Explicitly point Flask to the root static and templates folders
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
app = Flask(__name__, 
            template_folder=os.path.join(root_dir, 'templates'), 
            static_folder=os.path.join(root_dir, 'static'))

# Initialize Groq Engine with valid, open-weight production models
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Initialize Supabase Client for user management and authentication
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# Curated datasets for seamless offline/invalid-key testing in the US landscape
FALLBACK_CORPORATE_QUESTIONS = [
    "Thank you for joining this career simulation panel. US professional environments place a heavy emphasis on behavioral indicators. Let's begin by discussing a time when you had to manage competing deliverables or project constraints. What specific actions did you implement to ensure success?",
    "Could you walk me through a technical initiative you spearheaded where you encountered severe ambiguity? How did you define the project parameters and align your team?",
    "Describe a situation where you had a significant disagreement with a colleague or stakeholder on an architectural choice. How did you navigate the conflict to deliver results?"
]

FALLBACK_COLLEGE_QUESTIONS = [
    "Welcome to your admissions assessment simulation. US higher education institutions prioritize unique community contributions and holistic character. Could you describe a significant extracurricular initiative or academic challenge where you took the lead, and detail the personal growth you experienced as a result?",
    "Elite academic environments thrive on diverse perspectives. What unique facet of your background or personal journey will allow you to enrich our campus culture?",
    "Tell me about a time you failed to achieve a major personal or academic goal. How did you process that setback, and what structural changes did you make to your methodology moving forward?"
]

@app.route('/')
def home():
    """Renders the single-page glassmorphic user workspace dashboard."""
    return render_template('index.html', supabase_url=SUPABASE_URL, supabase_key=SUPABASE_KEY)

@app.route('/api/health', methods=['GET'])
def health_check():
    """Validates cloud service integrity and connection dependencies."""
    return jsonify({
        "status": "operational",
        "environment": "US-Standard-2026",
        "groq_connected": groq_client is not None,
        "supabase_connected": supabase is not None
    }), 200

@app.route('/api/auth/signup', methods=['POST'])
def auth_signup():
    """Handles email/password account creation using Supabase Auth."""
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required."}), 400

    if not supabase:
        return jsonify({"success": False, "error": "Supabase client is not configured. Check SUPABASE_URL and SUPABASE_KEY in .env."}), 500

    try:
        response = supabase.auth.sign_up({"email": email, "password": password})
        if response.user:
            return jsonify({
                "success": True,
                "user": {
                    "id": response.user.id,
                    "email": response.user.email
                },
                "session": response.session.access_token if response.session else None
            }), 200
        else:
            return jsonify({"success": False, "error": "User registration failed."}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/auth/signin', methods=['POST'])
def auth_signin():
    """Handles email/password authentication using Supabase Auth."""
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required."}), 400

    if not supabase:
        return jsonify({"success": False, "error": "Supabase client is not configured. Check SUPABASE_URL and SUPABASE_KEY in .env."}), 500

    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if response.user:
            return jsonify({
                "success": True,
                "user": {
                    "id": response.user.id,
                    "email": response.user.email
                },
                "session": response.session.access_token if response.session else None
            }), 200
        else:
            return jsonify({"success": False, "error": "Invalid email or password."}), 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/auth/google', methods=['POST'])
def auth_google():
    """Generates a Google OAuth authentication URL via Supabase and Google Cloud Console."""
    if not supabase:
        return jsonify({"success": False, "error": "Supabase client is not configured. Check SUPABASE_URL and SUPABASE_KEY in .env."}), 500

    try:
        data = request.get_json() or {}
        redirect_uri = data.get('redirect_to') or request.host_url.rstrip('/')
        res = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": redirect_uri
            }
        })
        url = getattr(res, 'url', None) or (res.get('url') if isinstance(res, dict) else None)
        if url:
            return jsonify({"success": True, "url": url}), 200
        else:
            return jsonify({"success": False, "error": "Could not generate Google OAuth URL."}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/auth/me', methods=['GET', 'POST'])
def auth_me():
    """Verifies access token and returns user details from Supabase Auth."""
    if not supabase:
        return jsonify({"success": False, "error": "Supabase client is not configured."}), 500

    auth_header = request.headers.get('Authorization', '')
    token = auth_header.replace('Bearer ', '').strip() if auth_header else ''

    if not token:
        data = request.get_json() or {}
        token = data.get('token', '').strip()

    if not token:
        return jsonify({"success": False, "error": "Access token is required."}), 400

    try:
        user_resp = supabase.auth.get_user(token)
        if user_resp and user_resp.user:
            return jsonify({
                "success": True,
                "user": {
                    "id": user_resp.user.id,
                    "email": user_resp.user.email
                }
            }), 200
        return jsonify({"success": False, "error": "Invalid or expired token."}), 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/session/start', methods=['POST'])
def start_session():
    """Dynamically generates a completely unique opening interview prompt based on the selected US track context, user resume, and target profile."""
    data = request.get_json() or {}
    track = data.get('track', 'General Corporate Interview')
    resume = data.get('resume', '').strip() or "Not provided"
    target_context = data.get('target_context', '').strip() or "General Targets"
    is_college = "college" in track.lower() or "admission" in track.lower()

    if not groq_client:
        initial_question = random.choice(FALLBACK_COLLEGE_QUESTIONS) if is_college else random.choice(FALLBACK_CORPORATE_QUESTIONS)
        return jsonify({
            "success": True,
            "track": track,
            "current_question": initial_question,
            "history": [
                {"role": "user", "content": f"Initialize simulation environment for track: {track}."},
                {"role": "assistant", "content": initial_question}
            ]
        }), 200

    if is_college:
        system_instruction = (
            "You are an elite US University Admissions Officer. "
            f"Target Institution/Program: {target_context}\n"
            f"Applicant Resume: {resume}\n"
            "CRITICAL RULES: DO NOT ask about their entire background. Pick exactly ONE specific extracurricular or academic detail from their resume and ask a single, highly concise opening question about it. Do not output greetings, prefaces, or extra text. Output only the short question."
        )
    else:
        system_instruction = (
            "You are a principal corporate recruiter. "
            f"Target Position: {target_context}\n"
            f"Candidate Resume: {resume}\n"
            "CRITICAL RULES: DO NOT ask a broad question about their entire resume. Pick exactly ONE specific project, role, or skill listed in their background and ask a single, concise behavioral question about it. Keep it brief. Do not output greetings, prefaces, or extra text. Output only the short question."
        )

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": "Please output the concise opening scenario question now."}
    ]

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=100
        )
        initial_question = completion.choices[0].message.content.strip()
    except Exception:
        initial_question = random.choice(FALLBACK_COLLEGE_QUESTIONS) if is_college else random.choice(FALLBACK_CORPORATE_QUESTIONS)

    return jsonify({
        "success": True,
        "track": track,
        "current_question": initial_question,
        "history": [
            {"role": "user", "content": f"Initialize simulation environment for track: {track}."},
            {"role": "assistant", "content": initial_question}
        ]
    }), 200

@app.route('/api/session/next', methods=['POST'])
def next_question():
    """Processes user response and formulates an adaptive follow-up question."""
    data = request.get_json() or {}
    history = data.get('history', [])
    track = data.get('track', 'General Corporate Interview')
    resume = data.get('resume', '').strip() or "Not provided"
    target_context = data.get('target_context', '').strip() or "General Targets"
    is_college = "college" in track.lower() or "admission" in track.lower()

    if not groq_client:
        next_q = random.choice(FALLBACK_COLLEGE_QUESTIONS) if is_college else random.choice(FALLBACK_CORPORATE_QUESTIONS)
        updated_history = history + [{"role": "assistant", "content": next_q}]
        return jsonify({
            "success": True,
            "next_question": next_q,
            "history": updated_history
        }), 200

    if is_college:
        context_guideline = (
            "You are an elite US University Admissions Officer. Review the conversation history to see what has already been discussed.\n"
            f"Target Context: {target_context}\n"
            f"Resume: {resume}\n"
            "CRITICAL RULES: Ask exactly ONE short, direct follow-up question. Either challenge their last response or pivot to a completely NEW, unexplored specific detail from their resume. Keep the question brief. Do not offer encouragement, feedback, or commentary. Output only the single question."
        )
    else:
        context_guideline = (
            "You are an expert technical recruiter. Review the conversation history to see what has already been discussed.\n"
            f"Target Context: {target_context}\n"
            f"Resume: {resume}\n"
            "CRITICAL RULES: Ask exactly ONE short, direct follow-up question. Either dig deeper into their last answer or pivot to a NEW, unexplored specific project/skill from their resume. Keep the question brief. Do not offer encouragement, feedback, or commentary. Output only the single question."
        )

    messages = [{"role": "system", "content": context_guideline}] + history

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.6,
            max_tokens=100
        )
        next_q = completion.choices[0].message.content.strip()
    except Exception:
        next_q = random.choice(FALLBACK_COLLEGE_QUESTIONS) if is_college else random.choice(FALLBACK_CORPORATE_QUESTIONS)

    updated_history = history + [{"role": "assistant", "content": next_q}]
    return jsonify({
        "success": True,
        "next_question": next_q,
        "history": updated_history
    }), 200

@app.route('/api/session/analyze', methods=['POST'])
def analyze_session():
    """Performs deep STAR behavioral framework breakdown, executive vocabulary critique, and structured insights."""
    data = request.get_json() or {}
    history = data.get('history', [])
    resume = data.get('resume', '').strip() or "Not provided"
    target_context = data.get('target_context', '').strip() or "General Targets"

    if not groq_client:
        return jsonify({
            "success": True,
            "critique": "## STAR Analysis\nGood start.\n\n## Vocabulary and Vibe\nNeeds work.\n\n## Strengths\n- Clear tone.\n\n## Weaknesses\n- Hesitant pacing.\n\n## How to Improve\n- Speak clearly.\n\n[SCORE: 65]"
        }), 200

    analysis_prompt = (
        "You are an expert executive coach specializing in US professional recruitment. "
        "Analyze the interview transcript and generate a structured evaluation report.\n\n"
        f"Declared Target Context: {target_context}\n"
        f"Candidate Background Record: {resume}\n\n"
        "CRITICAL RULES FOR FORMATTING:\n"
        "1. When giving your response, don't use words like \"the candidate\", rather use \"you\"."
        "2. DO NOT use numbered lists for the main sections. Use EXACTLY these Markdown headings:\n"
        "## STAR Analysis\n"
        "## Vocabulary and Vibe\n"
        "## Strengths\n"
        "## Weaknesses\n"
        "## How to Improve\n"
        "3. The 'STAR Analysis' section MUST be written as a paragraph of roughly 4 sentences explaining how well they structured their thoughts.\n"
        "4. The 'Vocabulary and Vibe' section MUST be written as a paragraph of roughly 3 sentences focusing on tone, filler words, and confidence.\n"
        "5. The 'Strengths', 'Weaknesses', and 'How to Improve' sections MUST each be formatted as a bulleted list containing EXACTLY 3 to 5 bullet points per section.\n"
        "6. At the very end of your response on a new line, you MUST output a final evaluation score out of 100. This score depends on how well the candidate performed on the STAR structure, vocabulary, and vibe. This score MUST be a multiple of 5 (e.g., 0, 5, 10, 15, ..., 95, 100). Format it exactly like this: [SCORE: XX]"
    )

    messages = [
        {"role": "system", "content": analysis_prompt},
        {"role": "user", "content": f"Interview Transcript Record for Evaluation:\n{history}"}
    ]

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3,
            max_tokens=900
        )
        critique = completion.choices[0].message.content.strip()
    except Exception as e:
        return jsonify({"success": False, "error": f"API Evaluation failed: {str(e)}"}), 500

    return jsonify({
        "success": True,
        "critique": critique
    }), 200

@app.route('/api/progress/summary', methods=['POST'])
def progress_summary():
    """Generates an overarching summary of a user's strengths and weaknesses across all historical sessions."""
    data = request.get_json() or {}
    history_texts = data.get('analyses', [])
    
    if not history_texts or not groq_client:
        return jsonify({"success": True, "summary": "Complete more sessions to generate an overall historical trend summary."}), 200
    
    # Concatenate past analyses (limit characters to avoid token limits on long histories)
    combined = "\n\n".join(history_texts)[:6000] 
    
    prompt = (
        "You are an expert executive coach. Read the following past interview evaluations for a candidate and summarize their OVERALL recurring patterns.\n"
        "Make sure to use \"you\" to make the report feel more personalized. Don't start every sentence with it, but use it when needed.\n"
        "Format EXACTLY like this with no extra text or pleasantries:\n"
        "**Overall Historical Strengths:**\n- [point 1]\n- [point 2]\n\n"
        "**Overall Recurring Weaknesses:**\n- [point 1]\n- [point 2]"
    )
    
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Past Evaluations Data:\n{combined}"}
            ],
            temperature=0.3, 
            max_tokens=400
        )
        return jsonify({"success": True, "summary": completion.choices[0].message.content.strip()}), 200
    except Exception:
        return jsonify({"success": False, "summary": "Failed to generate overall historical summary."}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)