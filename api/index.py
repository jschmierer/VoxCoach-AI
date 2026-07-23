import os
import random
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from groq import Groq
from supabase import create_client, Client

# Pull local tracking keys and configurations
load_dotenv()

app = Flask(__name__, template_folder='../templates')

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
            "You are an elite US University Admissions Officer. Generate exactly ONE unique, challenging, "
            "and highly realistic initial opening interview question designed for an elite college applicant.\n"
            f"Target Institution/Program: {target_context}\n"
            f"Applicant Resume/Core Experiences: {resume}\n"
            "Incorporate and personalize the question based on their unique background while focusing on themes of holistic character, "
            "community contribution, or personal growth. Do not output greetings, prefaces, or extra text. Output only the single question."
        )
    else:
        system_instruction = (
            "You are a principal corporate recruiter managing high-stakes behavioral screening loops in the US market. "
            "Generate exactly ONE unique, realistic, and highly professional initial interview question targeting "
            "a candidate's behavioral history (e.g., leadership, dealing with ambiguity, or project failures).\n"
            f"Target Position/Job Description: {target_context}\n"
            f"Candidate Resume/Core Experiences: {resume}\n"
            "Tailor the question specifically to their declared experience background and target role. "
            "Do not output greetings, prefaces, or extra text. Output only the single question."
        )

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": "Please output the personalized opening scenario question now."}
    ]

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=150
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
            "You are an elite US University Admissions Officer. The user is an applicant. Review the conversation history.\n"
            f"Target Institution/Program Context: {target_context}\n"
            f"Applicant Background Context: {resume}\n"
            "Ask exactly ONE incisive, direct follow-up question that builds naturally on their last response, challenges gaps in their narrative, "
            "or moves to a related holistic candidate evaluation metric. Keep their application target and background in perspective. "
            "Do not offer encouragement, feedback, or commentary. Output only the single question."
        )
    else:
        context_guideline = (
            "You are an expert technical recruiter interviewing a candidate for a highly competitive US corporate role. Review the conversation history.\n"
            f"Target Position/Role Context: {target_context}\n"
            f"Candidate Background Context: {resume}\n"
            "Ask exactly ONE incisive, professional follow-up question digging into specific technical decisions, behavioral actions, or metrics from their last answer. "
            "Do not offer encouragement, feedback, or commentary. Output only the single question."
        )

    messages = [{"role": "system", "content": context_guideline}] + history

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.6,
            max_tokens=150
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
    """Performs deep STAR behavioral framework breakdown, executive vocabulary critique, and strategic action items."""
    data = request.get_json() or {}
    history = data.get('history', [])
    resume = data.get('resume', '').strip() or "Not provided"
    target_context = data.get('target_context', '').strip() or "General Targets"

    if not groq_client:
        return jsonify({
            "success": True,
            "critique": "### Evaluation Matrix Output\n"
                        "1. **STAR Methodology Standard**: Delivery shows adequate response formulation, but missing quantified outcome metrics.\n"
                        "2. **Pacing & Structural Flow**: Moderate cadence observed. Avoid long pauses during transitions.\n"
                        "3. **Executive Vocabulary**: Transition from weak hedging terms ('I think', 'just') to direct command verbs ('Led', 'Architected').\n"
                        "4. **Growth Strategy**: Quantify impacts and structure answers with clear Situation, Task, Action, Result segments."
        }), 200

    analysis_prompt = (
        "You are an expert executive coach specializing in US professional recruitment trends and Ivy League admissions criteria. "
        "Analyze the provided interview transcript history and generate a structured evaluation report formatted cleanly in Markdown.\n\n"
        f"Declared Target Context: {target_context}\n"
        f"Candidate Background Record: {resume}\n\n"
        "Please structure your assessment under the following exact section headers:\n"
        "## 1. STAR Behavioral Methodology Analysis\n"
        "Assess how effectively the candidate articulated Situation, Task, Action, and Result. Identify missing metrics or vague resume experiences.\n\n"
        "## 2. Structural Delivery Breakdown\n"
        "Evaluate pacing, clarity of transitions, and the logical flow of arguments across conversation turns.\n\n"
        "## 3. Vocabulary & Executive Presence Vibe Check\n"
        "Perform a deep vocabulary analysis. Specifically pinpoint any passive, weak, or defensive phrases used (e.g., 'I just helped', 'I think we did', 'sort of') and map out a customized selection of strong, active power verbs (e.g., 'Spearheaded', 'Architected', 'Orchestrated') to amplify delivery command.\n\n"
        "## 4. High-Impact Strategies for Growth\n"
        "Provide exactly three actionable, highly tailored strategies for immediate performance scaling."
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
            max_tokens=1000
        )
        critique = completion.choices[0].message.content.strip()
    except Exception as e:
        return jsonify({"success": False, "error": f"API Evaluation failed: {str(e)}"}), 500

    return jsonify({
        "success": True,
        "critique": critique
    }), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)