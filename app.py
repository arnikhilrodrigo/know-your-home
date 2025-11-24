import streamlit as st
import openai
import os
import json
from dotenv import load_dotenv

# -------------------------------------------------
# Load Environment Variables
# -------------------------------------------------
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# -------------------------------------------------
# Streamlit Page Config
# -------------------------------------------------
st.set_page_config(page_title="Know Your Home", page_icon="🏡", layout="centered")

# -------------------------------------------------
# Custom CSS for Card-style UI
# -------------------------------------------------
st.markdown("""
    <style>
    .kyh-main {
        max-width: 900px;
        margin: 0 auto;
        padding-top: 1rem;
    }
    .kyh-card {
        background-color: #FFFFFF;
        border-radius: 18px;
        padding: 1.5rem 1.75rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.04);
        margin-bottom: 1.5rem;
        border: 1px solid rgba(142,124,195,0.12);
    }
    .kyh-title {
        font-size: 1.6rem;
        font-weight: 700;
        color: #4A3B91;
        margin-bottom: 0.25rem;
    }
    .kyh-subtitle {
        font-size: 0.95rem;
        color: #555;
        margin-bottom: 0.5rem;
    }
    .kyh-step-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #8E7CC3;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    .kyh-section-title {
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 0.75rem;
        color: #4A3B91;
    }
    .kyh-divider {
        height: 1px;
        background: linear-gradient(to right, rgba(142,124,195,0.5), transparent);
        margin: 0.75rem 0 1rem 0;
    }
    .kyh-report {
        border-left: 4px solid #8E7CC3;
        padding-left: 1rem;
    }
    .stButton>button {
        border-radius: 999px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        border: none;
    }
    </style>
""", unsafe_allow_html=True)

# Wrap whole app in a centered container
st.markdown('<div class="kyh-main">', unsafe_allow_html=True)

# -------------------------------------------------
# Area + Cost Calculation Logic
# -------------------------------------------------
def compute_areas(bhk: str, plot_size: float, workspace: str, rental: str, answers: dict):
    """
    Compute bedrooms, bathrooms, dynamic room sizes, carpet, built-up, plinth and cost.
    All arithmetic lives here so GPT only formats, never calculates.
    """

    # Map BHK to number of bedrooms
    bhk_map = {"2 BHK": 2, "3 BHK": 3, "4 BHK": 4}
    bedrooms = bhk_map.get(bhk, 2)

    # Bathrooms rule: at least 2, and 4 BHK => 3 minimum etc.
    bathrooms = max(2, bedrooms - 1)

    # ---- Base sizes (sq.ft) ----
    BED = 150         # standard bedroom
    BATH = 50         # standard bathroom

    # Living room – grow if they host often
    LIVING = 180
    if answers.get("Q9") == "Yes, frequently 🎉" or answers.get("Q12") == "Yes, large gatherings":
        LIVING = 220
    elif answers.get("Q10") in ["Terrace parties 🌌", "Indoor gatherings 🍽️"]:
        LIVING = 200

    # Kitchen – slightly larger if social / cooking heavy
    KITCHEN = 70
    if answers.get("Q10") == "Indoor gatherings 🍽️":
        KITCHEN = 80

    CAR_PARK = 150  # for table only, not included in carpet/built-up

    # Workspace – size depends on WFH pattern
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

    # Rental / commercial portion
    RENTAL_SIZE = 250 if rental.lower() == "yes" else 0

    # Outdoor / balcony / garden – only if strongly indicated
    OUTDOOR_SIZE = 0
    if answers.get("Q2") == "Gardening or tending to plants 🌱" or answers.get("Q15") == "Must have garden/balcony 🌿":
        OUTDOOR_SIZE = 60

    # Floors heuristic: 2 floors for 3/4 BHK, 1 floor for 2 BHK
    if bedrooms >= 3:
        floors = 2
    else:
        floors = 1

    STAIR_PER_FLOOR = 75
    STAIR_TOTAL = STAIR_PER_FLOOR * floors

    # ---- Carpet areas ----
    # Carpet WITHOUT staircase (usable spaces)
    carpet_without_stair = (
        bedrooms * BED
        + bathrooms * BATH
        + LIVING
        + KITCHEN
        + WORKSPACE_SIZE
        + RENTAL_SIZE
        + OUTDOOR_SIZE
    )

    # Add staircase block to functional area
    carpet_area = carpet_without_stair + STAIR_TOTAL

    # Built-up = carpet (incl. stair) + 10% for walls / circulation
    built_up_area = round(carpet_area * 1.10)

    # Plinth = 80% of plot area as per your rule
    plinth_area = round(float(plot_size) * 0.8)

    # Construction cost
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

# -------------------------------------------------
# Welcome Screen
# -------------------------------------------------
st.markdown("""
<div class="kyh-card">
  <div class="kyh-step-label">Pocket Home · Pre-Design Clarity</div>
  <div class="kyh-title">🏡 Know Your Home</div>
  <div class="kyh-subtitle">
    Before you start drawing plans or talking to contractors, let’s first understand how you actually live.
    Your answers will help you see what kind of home truly fits your lifestyle, plot and budget.
  </div>
</div>
""", unsafe_allow_html=True)

if "started" not in st.session_state:
    st.session_state.started = False
if not st.session_state.started:
    with st.container():
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(
                '<div class="kyh-card"><b>Ready?</b><br/>This will take just a few minutes and give you a clear, shareable brief for your future home.</div>',
                unsafe_allow_html=True
            )
            start = st.button("✨ Begin My Home Journey")
        # col2 left empty for balance
    if start:
        st.session_state.started = True
    else:
        st.stop()

# -------------------------------------------------
# User Info (Step 1)
# -------------------------------------------------
st.markdown("""
<div class="kyh-card">
  <div class="kyh-step-label">Step 1</div>
  <div class="kyh-section-title">Basic Information</div>
""", unsafe_allow_html=True)

name = st.text_input("Your Name")
email = st.text_input("Email")
own_plot = st.radio("Do you already own a plot?", ["Yes", "No"], horizontal=True)

if own_plot == "Yes":
    plot_size = st.number_input("Enter your plot size (sq.ft)", 500, 5000, 1200)
else:
    plot_size = st.number_input("Ideal plot size you are considering (sq.ft)", 500, 5000, 1200)

col_b1, col_b2 = st.columns(2)
with col_b1:
    budget = st.number_input("Your Estimated Construction Budget (₹)", 0, 20000000, 3500000)
with col_b2:
    family_members = st.number_input("Family Members", 1, 10, 3)

col_b3, col_b4 = st.columns(2)
with col_b3:
    bhk = st.radio("How many bedrooms are you planning for?", ["2 BHK", "3 BHK", "4 BHK"], horizontal=True)
with col_b4:
    workspace = st.radio("Workspace / Walk-in in bedroom?", ["Yes", "No"], horizontal=True)

rental = st.radio("Include a rental / studio portion?", ["Yes", "No"], horizontal=True)

st.markdown("</div>", unsafe_allow_html=True)  # close Step 1 card

# -------------------------------------------------
# Lifestyle Questions (Step 2 - 21 Questions)
# -------------------------------------------------
st.markdown("""
<div class="kyh-card">
  <div class="kyh-step-label">Step 2</div>
  <div class="kyh-section-title">Lifestyle & Design Preferences</div>
  <div class="kyh-divider"></div>
""", unsafe_allow_html=True)

answers = {}

# SECTION A – Everyday Rhythm
answers["Q1"] = st.radio("Which moment feels most ‘you’ at home?",
    ["Coffee on the balcony ☕","Family dinner 🍲","Quiet reading 📖","Movie night 🍿"])
answers["Q2"] = st.radio("Your ideal Sunday at home would be...",
    ["Gardening or tending to plants 🌱","Hosting brunch with friends 🥂","Sleeping in ☀️","A short drive 🚗"])
answers["Q3"] = st.radio("When you get back from work, what’s the first feeling you seek?",
    ["Calm and peace 🌿","Energy and warmth ❤️","A creative recharge 💡","A cozy personal cocoon 🛋️"])
answers["Q4"] = st.radio("Which space defines comfort for you the most?",
    ["Living room with a swing 🪑","Bedroom with natural light 🌞","Balcony with plants 🌿","Courtyard with sky above ⛅"])

# SECTION B – Culture & Tradition
answers["Q5"] = st.radio("Would you love to keep cultural elements alive in your home?",
    ["Yes, like a Kolam or Tulasi courtyard 🌸","A small pooja/meditation corner 🕯️","Maybe a minimal version","No, prefer fully contemporary"])
answers["Q6"] = st.radio("How important is a swing (‘oonjal’) inside the home?",
    ["Definitely! It adds soul 💫","Nice to have","Not for me"])
answers["Q7"] = st.radio("Would you like your entrance to feel...",
    ["Warm & traditional 🌺","Clean & modern 🧱","A blend of both"])
answers["Q8"] = st.radio("Do you prefer a courtyard or skylight feature?",
    ["Yes, both 🌞","Only skylight","Only courtyard","Not needed"])

# SECTION C – Family, Gatherings & Events
answers["Q9"] = st.radio("Do you often host get-togethers or celebrations at home?",
    ["Yes, frequently 🎉","Occasionally","Rarely"])
answers["Q10"] = st.radio("How do you usually celebrate special occasions?",
    ["Terrace parties 🌌","Indoor gatherings 🍽️","Quiet family rituals 🪔"])
answers["Q11"] = st.radio("Would you love a cozy home theatre or media setup?",
    ["Yes, Netflix weekends are sacred 🎬","Sometimes, not dedicated","No, prefer shared areas"])
answers["Q12"] = st.radio("Do you invite friends/family for events like IPL or Diwali?",
    ["Yes, large gatherings","Only close friends","Rarely"])
answers["Q13"] = st.radio("Do parents or grandparents visit or live with you often?",
    ["They stay with us","They visit occasionally","Mostly independent"])

# SECTION D – Design & Future Growth
answers["Q14"] = st.radio("What’s your preferred architectural vibe?",
    ["Traditional (Madras terrace, courtyards, woodwork)","Contemporary minimal","Balanced fusion"])
answers["Q15"] = st.radio("How important is your connection to outdoors?",
    ["Must have garden/balcony 🌿","Moderate","Prefer enclosed interiors"])
answers["Q16"] = st.radio("Are you conscious about sustainability and materials?",
    ["Yes, prefer local materials 🌾","Somewhat","Not a priority"])
answers["Q17"] = st.radio("Would you like your home to adapt over time?",
    ["Yes, plan future expansion 🔄","Maybe minor flexibility","Fixed setup"])
answers["Q18"] = st.radio("Would you like to include a small commercial/rental space?",
    ["Yes, rental or studio","Maybe later","No, only residence"])

# SECTION E – Lifestyle & Energy
answers["Q19"] = st.radio("Do you or your spouse work from home regularly?",
    ["Yes, need a home office 💻","Occasionally","Not required"])
answers["Q20"] = st.radio("How would you describe your social energy?",
    ["Love having people over 🎊","Prefer small gatherings ☕","Enjoy solitude 🌙"])
answers["Q21"] = st.text_input("If you had to describe your dream home in one word, what would it be?",
    placeholder="Peace, Warmth, Freedom...")

st.markdown("</div>", unsafe_allow_html=True)  # close Step 2 card

# -------------------------------------------------
# Generate Report
# -------------------------------------------------
generate = st.button("🏗️ Generate My Home Report")

if generate:
    st.info("Building your personalised home report... please wait ⏳")

    # Compute areas + cost deterministically
    calc = compute_areas(bhk, plot_size, workspace, rental, answers)

    payload = {
        "name": name, "email": email, "own_plot": own_plot,
        "plot_size": plot_size, "budget": budget,
        "family_members": family_members, "bhk": bhk,
        "workspace": workspace, "rental": rental,
        "answers": answers,
        "calc": calc
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
    {json.dumps(payload, indent=2)}

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
        st.success("✅ Your report is ready!")

        st.markdown("""
        <div class="kyh-card kyh-report">
          <div class="kyh-section-title">Your Personalised Home Report</div>
        """, unsafe_allow_html=True)
        st.markdown(report)
        st.markdown("</div>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error: {e}")

# Close main container
st.markdown('</div>', unsafe_allow_html=True)
