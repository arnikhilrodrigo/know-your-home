from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import openai
import os
import json

# -------------------------------------------------
# Setup
# -------------------------------------------------
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI(
    title="Know Your Home API",
    description="Backend API for Know Your Home - generates lifestyle-based home reports",
    version="1.0.0"
)

# Allow CORS for your Lovable frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to your Lovable app domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# Request Schema
# -------------------------------------------------
class UserInput(BaseModel):
    name: str
    email: str
    own_plot: str
    plot_size: float
    budget: float
    family_members: int
    bhk: str
    workspace: str
    rental: str
    answers: dict

# -------------------------------------------------
# Root Endpoint
# -------------------------------------------------
@app.get("/")
def home():
    return {"message": "🏡 Know Your Home API is running!"}

# -------------------------------------------------
# Report Generation Endpoint
# -------------------------------------------------
@app.post("/generate-report")
async def generate_report(data: UserInput):
    try:
        # Construct AI prompt
        prompt = f"""
        You are a friendly architect from Nichekala writing directly to the user.
        Prepare a **personalised home insight report** with a mix of clarity, hope, and inspiration.

        Always speak in 2nd person ("you", "your home", "your lifestyle"). Never use "he" or "she".

        --- PART 1: YOUR HOME INSIGHT ---
        - Begin warmly, acknowledging that building a home is a milestone filled with emotions and possibilities.
        - Reflect what the user’s lifestyle choices reveal — whether they value light, openness, social spaces, calm corners, or culture.
        - Suggest 4–6 design directions that would suit them (like a swing in the living, skylight above the dining, a terrace for birthdays, or space for parents).
        - Keep tone engaging, relatable, and realistic. Make it sound like a personal guidance note.

        --- PART 2: AREA STATEMENT ---
        Create a Markdown table:
        | Space | Suggested Size (sq.ft) | Type |
        Reference:
        Bedroom: 100–120 (compact) / 150–200 (standard)
        Living: 150–216
        Kitchen: 64–80
        Bathroom: 40–60
        Car park: 135–160
        +30 sqft if workspace/walk-in is “Yes”
        +250 sqft if rental/commercial is “Yes”
        Built-up area = sum of all + additions
        Plinth area = plot area × 0.8
        Output total built-up and plinth areas below the table.

        --- PART 3: BUDGET REFLECTION ---
        Construction Cost = (Plinth area + Built-up area) × ₹2500/sq.ft
        Add 10% to this cost and show a **range**: from base to 10% higher.
        Compare with the user’s budget ₹{data.budget}.
        Speak directly to the user:
          - If within budget → encourage and appreciate the balance.
          - If slightly above → suggest phase-wise plan, or compact adjustments.
          - If over → provide reassurance and options to make it feasible.
        End warmly with:
        “Your home can grow with you — it’s about planning smart, not cutting dreams short.”

        USER DATA:
        {json.dumps(data.dict(), indent=2)}
        """

        # OpenAI Call
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )

        report = response.choices[0].message.content

        return {
            "status": "success",
            "name": data.name,
            "email": data.email,
            "report": report
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
