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
    return render_template('index.html')

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
    """Generates a Google OAuth authentication URL via Supabase and Google Cloud Consult."""
    if not supabase:
        return jsonify({"success": False, "error": "Supabase client is not configured. Check SUPABASE_URL and SUPABASE_KEY in .env."}), 500

    try:
        redirect_uri = request.host_url.rstrip('/')
        res = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": redirect_uri
            }
        })
        return jsonify({"success": True, "url": res.url}), 200
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
            "Tailor the question directly to target specific behavioral actions relevant to their background and the destination role. "
            "Do not output greetings, prefaces, or extra text. Output only the single question."
        )

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": system_instruction}],
            temperature=0.85,
            max_tokens=150
        )
        initial_question = completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Groq API connection drop: {e}. Falling back to local curated dataset pools.")
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

@app.route('/api/session/respond', methods=['POST'])
def process_response():
    """Processes user text turns and evaluates conversational history to return the next adaptive question."""
    data = request.get_json() or {}
    transcript = data.get('transcript', '')
    history = data.get('history', [])
    track = data.get('track', 'General Corporate Interview')
    resume = data.get('resume', '').strip() or "Not provided"
    target_context = data.get('target_context', '').strip() or "General Targets"
    is_college = "college" in track.lower() or "admission" in track.lower()
    
    cleaned_transcript = transcript.strip()
    if not cleaned_transcript:
        return jsonify({"success": False, "error": "No new transcript text provided to advance the session conversation."}), 400
        
    # Commit the user response explicitly to history log tracking if not already present
    if not history or history[-1].get('content') != cleaned_transcript:
        history.append({"role": "user", "content": cleaned_transcript})
    
    if not groq_client:
        fallback_question = random.choice(FALLBACK_COLLEGE_QUESTIONS) if is_college else random.choice(FALLBACK_CORPORATE_QUESTIONS)
        next_question = f"[Fallback mode active due to missing API configuration] {fallback_question}"
        history.append({"role": "assistant", "content": next_question})
        return jsonify({"success": True, "next_question": next_question, "history": history}), 200

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
            f"Target Position Context: {target_context}\n"
            f"Candidate Background Context: {resume}\n"
            "Ask exactly ONE professional follow-up question that builds on their story or probes for missing elements of the STAR method "
            "(metrics, actions, results) specific to their domain. Do not offer validation or filler phrases. Output only the question."
        )
    
    messages = [{"role": "system", "content": context_guideline}]
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.7,
            max_tokens=150
        )
        next_question = completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Groq API failure during response: {e}")
        fallback_question = random.choice(FALLBACK_COLLEGE_QUESTIONS) if is_college else random.choice(FALLBACK_CORPORATE_QUESTIONS)
        next_question = f"[API Connection Glitch - Fallback Prompt] {fallback_question}"
        
    history.append({"role": "assistant", "content": next_question})
    return jsonify({
        "success": True,
        "next_question": next_question,
        "history": history
    }), 200

@app.route('/api/session/analyze', methods=['POST'])
def analyze_session():
    """Generates the comprehensive review metrics matrix on demand without terminating or freezing active workspace states."""
    data = request.get_json() or {}
    history = data.get('history', [])
    resume = data.get('resume', '').strip() or "Not provided"
    target_context = data.get('target_context', '').strip() or "General Targets"
    
    if not groq_client:
        return jsonify({
            "success": True,
            "analysis": "## 1. Content Quality Score & Evaluation\nLocal fallback mode is currently running because no valid GROQ_API_KEY was detected in your root .env file configuration.\n\n## 2. Structural Delivery Breakdown\nYour client-side speech processing mechanics (Words Per Minute metrics, Fluency Pauses, and Filler Word counters) are fully operational.\n\n## 3. Vocabulary & Executive Presence Vibe Check\nLive AI-powered analysis of structural speech patterns, tone metrics, passive phrase extractions, and power word suggestions requires a connected Groq API engine key configuration.\n\n## 4. High-Impact Strategies for Growth\n1. Populate your .env file with a valid Groq API authorization key to access live AI coaching reports.\n2. Ensure your vocal speech tracks adhere cleanly to the behavioral STAR structural framework.\n3. Keep monitoring the live dashboard tickers during speech delivery."
        }), 200
        
    analysis_prompt = (
        "You are an expert executive coach specializing in US professional recruitment trends and Ivy League admissions criteria. "
        "Perform a comprehensive evaluation on the provided interview dialogue exchange.\n"
        f"Target Application Goal: {target_context}\n"
        f"Provided Resume/Background Parameters: {resume}\n"
        "Analyze the response depth, logical cohesion, and mapping to target benchmarks (like the STAR methodology or authentic leadership).\n\n"
        "Format your diagnostic breakdown clearly using the following four distinct headers with clean spacing:\n\n"
        "## 1. Content Quality Score & Evaluation\n"
        "Critique the substance of the responses given so far. Assess the balance between concrete project metrics, narrative value, and how well they leverage their past resume experiences.\n\n"
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
        "analysis": critique
    }), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)