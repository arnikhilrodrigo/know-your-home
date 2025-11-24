import os
import json
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI(title="Know Your Home Backend")

# Allow CORS so Lovable frontend can call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # you can restrict later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Models ----------

class KYHPayload(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    own_plot: str
    plot_size: float
    budget: float
    family_members: Optional[int] = None
    bhk: str
    workspace: str
    rental: str
    answers: Dict[str, str]


# ---------- Area + Cost Logic (same philosophy as Streamlit app) ----------

def compute_areas(bhk: str, plot_size: float, workspace: str, rental: str, answers: Dict[str, str]):
    bhk_map = {"2 BHK": 2, "3 BHK": 3, "4 BHK": 4}
    bedrooms = bhk_map.get(bhk, 2)

    # Bathrooms: at least 2, for 4 BHK at least 3, etc.
    bathrooms = max(2, bedrooms - 1)

    # Base sizes
    BED = 150        # standard bedroom
    BATH = 50
    LIVING = 180
    KITCHEN = 70
    CAR_PARK = 150

    # Boost living if they host often
    if answers.get("Q9") == "Yes, frequently 🎉" or answers.get("Q12") == "Yes, large gatherings":
        LIVING = 220
    elif answers.get("Q10") in ["Terrace parties 🌌", "Indoor gatherings 🍽️"]:
        LIVING = 200

    # Bigger kitchen for indoor gatherings
    if answers.get("Q10") == "Indoor gatherings 🍽️":
        KITCHEN = 80

    # Workspace sizing
    if workspace.lower() == "yes":
        q19 = answers.get("Q19", "")
        if q19 == "Yes, need a home office 💻":
            WORKSPACE_SIZE = 80
        elif q19 == "Occasionally":
            WORKSPACE_SIZE = 40
        else:
            WORKSPACE_SIZE = 30
    else:
        WORKSPACE_SIZE = 0

    # Rental / commercial
    RENTAL_SIZE = 250 if rental.lower() == "yes" else 0

    # Outdoor / balcony / garden
    OUTDOOR_SIZE = 0
    if answers.get("Q2") == "Gardening or tending to plants 🌱" or answers.get("Q15") == "Must have garden/balcony 🌿":
        OUTDOOR_SIZE = 60

    # Floors heuristic: 2 floors for 3/4 BHK, 1 floor for 2 BHK
    floors = 2 if bedrooms >= 3 else 1
    STAIR_PER_FLOOR = 75
    STAIR_TOTAL = STAIR_PER_FLOOR * floors

    carpet_without_stair = (
        bedrooms * BED
        + bathrooms * BATH
        + LIVING
        + KITCHEN
        + WORKSPACE_SIZE
        + RENTAL_SIZE
        + OUTDOOR_SIZE
    )

    carpet_area = carpet_without_stair + STAIR_TOTAL
    built_up_area = round(carpet_area * 1.10)         # +10% for walls/circulation
    plinth_area = round(float(plot_size) * 0.8)       # 80% of plot

    base_cost = (built_up_area + plinth_area) * 2500
    cost_low = round(base_cost)
    cost_high = round(base_cost * 1.10)

    return {
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "floors": floors,
        "sizes": {
            "bedroom": BED,
            "bathroom": BATH,
            "living": LIVING,
            "kitchen": KITCHEN,
            "car_park": CAR_PARK,
            "workspace": WORKSPACE_SIZE,
            "rental": RENTAL_SIZE,
            "outdoor": OUTDOOR_SIZE,
            "staircase": STAIR_PER_FLOOR,
        },
        "carpet_without_stair": carpet_without_stair,
        "stair_total": STAIR_TOTAL,
        "carpet_area": carpet_area,
        "built_up_area": built_up_area,
        "plinth_area": plinth_area,
        "cost_low": cost_low,
        "cost_high": cost_high,
    }


# ---------- Routes ----------

@app.get("/")
def root():
    return {"status": "ok", "message": "Know Your Home backend is running."}


@app.post("/generate-report")
def generate_report(payload: KYHPayload):
    if not openai.api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    calc = compute_areas(
        payload.bhk,
        payload.plot_size,
        payload.workspace,
        payload.rental,
        payload.answers,
    )

    full_payload = {
        "name": payload.name,
        "email": payload.email,
        "own_plot": payload.own_plot,
        "plot_size": payload.plot_size,
        "budget": payload.budget,
        "family_members": payload.family_members,
        "bhk": payload.bhk,
        "workspace": payload.workspace,
        "rental": payload.rental,
        "answers": payload.answers,
        "calc": calc,
    }

    prompt = f"""
    You are a friendly architect from Nichekala writing directly to the user.
    Prepare a **personalised home insight report** with a mix of clarity, hope, and realistic guidance.

    Always speak in 2nd person ("you", "your home", "your lifestyle"). Never use "he" or "she".

    IMPORTANT — STRICT NUMERIC RULE:
    All area and cost values are already calculated in the JSON under the key "calc".
    You MUST NOT invent, estimate, or modify any numbers.
    Use ONLY the values from "calc". Do NOT create your own ranges or formulas.

    --- JSON DATA (source of truth) ---
    {json.dumps(full_payload, indent=2)}

    --- PART 1: YOUR HOME INSIGHT ---
    - Begin warmly, acknowledging that building a home is a milestone.
    - Reflect what the user’s lifestyle choices reveal — whether they value light, openness, social spaces, calm corners, culture, or outdoors.
    - Suggest 4–6 design directions that would suit them (like a swing in the living, skylight above the dining, a terrace for birthdays, a balcony garden, or space for parents).
    - Keep tone engaging, relatable, and realistic. Make it sound like a personal guidance note, not a poem.

    --- PART 2: AREA STATEMENT (STRICT FORMAT) ---
    Create a Markdown table EXACTLY in this pattern:

    | Space         | Quantity | Size (sq.ft) | Subtotal (sq.ft) |
    |--------------|---------:|-------------:|-----------------:|

    Use these rows and ONLY these calculations:
    - Bedrooms → quantity = calc["bedrooms"], size = calc["sizes"]["bedroom"], subtotal = quantity * size
    - Bathrooms → quantity = calc["bathrooms"], size = calc["sizes"]["bathroom"], subtotal = quantity * size
    - Living → quantity = 1, size = calc["sizes"]["living"], subtotal = size
    - Kitchen → quantity = 1, size = calc["sizes"]["kitchen"], subtotal = size
    - Workspace → include ONLY if calc["sizes"]["workspace"] > 0
    - Rental space → include ONLY if calc["sizes"]["rental"] > 0
    - Outdoor / Balcony / Garden → include ONLY if calc["sizes"]["outdoor"] > 0
    - Staircase block → quantity = calc["floors"], size = calc["sizes"]["staircase"], subtotal = quantity * size
    - Car park → show as a row with quantity = 1, size = calc["sizes"]["car_park"], but EXCLUDE it from any carpet/built-up totals (informational only).

    After the table, clearly show:
    - Interior usable area (excluding staircase) = calc["carpet_without_stair"] sq.ft
    - Total functional area (including staircase) = calc["carpet_area"] sq.ft
    - Built-Up Area = calc["built_up_area"] sq.ft
    - Plinth Area = calc["plinth_area"] sq.ft

    Do NOT change these numbers or recompute them. Just explain them in simple language.

    --- PART 3: BUDGET REFLECTION ---
    Use EXACTLY:
    - Base Construction Cost = calc["cost_low"]
    - Higher Range (with +10%) = calc["cost_high"]

    These are calculated from the formula:
    Construction Cost = (Built-up Area + Plinth Area) × ₹2500/sq.ft
    then adding 10% on top for the higher range.

    Compare the user’s budget (payload["budget"]) ONLY with this cost range:
      - If budget is within the range → say it’s well aligned and allows reasonable choices.
      - If budget is below cost_low → say the dream is slightly above the current budget and suggest options: phasing, compact planning, or material choices.
      - If budget is above cost_high → say they have room to explore better finishes or some future-proofing.

    End warmly with:
    “Your home can grow with you — it’s about planning smart, not cutting dreams short.”
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        report = response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"report": report, "calc": calc}
