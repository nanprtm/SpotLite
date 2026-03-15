# SpotLite

**Voice-powered stage design assistant for Indonesian theater**

SpotLite is a web application that helps theater directors design stage sets through real-time voice conversation with an AI set designer. Directors describe their vision aloud and receive AI-generated mockup images, an itemized bill of materials with real Indonesian prices, automated vendor sourcing, and nearby thrift store suggestions — all within a specified budget.

---

## Problem Statement

Musical theater in Indonesia has a dirty secret: student productions and indie shows regularly go bankrupt ("boncos"). They want to build something extravagant, but only have limited knowledge to materials recommended by word of mouth, something that is often beyond their budget. They sketch on paper, call vendors for quotes, get sticker shock, and either blow their budget or water down their vision. We wanted to give them a tool that feels like brainstorming with a brilliant, budget-savvy friend — not filling out spreadsheets.

## Solution

SpotLite is a web app where theater directors have a real-time voice conversation with Gemini to design their set within a budget. The AI persona "SpotLite" acts as an energetic, creative set designer who understands local materials, costs, and creative workarounds. Gemini generates updated stage mockup images, an itemized bill of materials with real Indonesian material prices, and automatically searches for vendors on Tokopedia, Shopee, and Bukalapak. It also finds nearby thrift/junkyard stores for cheaper secondhand materials. Directors can iterate conversationally — asking to make things cheaper, swap materials, or redesign sections — and see both the visual and cost impact in real time.

---

## Architecture

```
+--------------------------------------------------------------+
|                         Browser                               |
|  Camera + Mic + Geolocation → WebSocket → Bento Grid UI      |
|  [Stage Image] [BOM Table] [Vendor Panel] [Chat]             |
+-----------------------------+--------------------------------+
                              | WebSocket (audio, photos, results)
+-----------------------------v--------------------------------+
|              FastAPI Backend (Cloud Run)                       |
|                                                               |
|  ADK Runner ↔ Gemini Live API (voice streaming)               |
|        | function calls                                       |
|  ┌─────┴──────────────────────────────┐                       |
|  │ generate_stage_image               │ Background async      |
|  │ estimate_bom → auto vendor search  │ Sequential + delayed  |
|  │ search_vendors (Google Search)     │ Grounding API         |
|  │ thrift store search                │ Location-aware        |
|  └────────────────────────────────────┘                       |
|  Price Database (58 items from juraganmaterial.id)             |
+---------------------------------------------------------------+
```

**Key technical details:**

- **Framework:** Google ADK (Agent Development Kit) with Runner, InMemorySessionService, LiveRequestQueue
- **Live API model:** `gemini-live-2.5-flash-native-audio` for real-time voice streaming
- **Image model:** `gemini-2.5-flash-image` with 16:9 aspect ratio
- **Vendor search model:** `gemini-2.5-flash` with Google Search grounding
- **Auth:** Vertex AI with Google Cloud Application Default Credentials
- **Session management:** ADK SessionResumptionConfig handles automatic reconnection
- **Image generation:** Runs as background async task to avoid blocking the Live session. Includes retry with exponential backoff on rate limits.
- **Vendor auto-trigger:** After BOM generation, automatically searches vendors for top 3 most expensive items (sequential with delays to avoid rate limits)
- **Thrift store search:** Location-aware search for nearby junkyard/secondhand stores
- **Audio playback:** Gapless scheduling via Web Audio API `source.start(nextPlayTime)`

**Data flow:**

1. Director opens the app, enters show details (name, stage dimensions, budget, city/region), and starts a session.
2. A WebSocket connection is established to the FastAPI backend. Browser geolocation auto-detects the city.
3. A placeholder stage image is displayed. The director can capture their real stage via camera.
4. The director taps the mic and describes what they want on stage.
5. SpotLite generates the visualization when the request is clear, or asks clarifying questions if vague.
6. Gemini triggers function calls:
   - `generate_stage_image` — background async task, calls Gemini image model
   - `estimate_bom` — matches materials via fuzzy matching, auto-corrects quantities based on stage dimensions
7. After BOM generation, vendor searches auto-trigger in the background:
   - Top 3 items by cost → searched on Tokopedia, Shopee, Bukalapak
   - Thrift/junkyard stores near the director's city
8. Results stream to the browser in real-time: audio, images, BOM table, vendor cards, thrift stores.

---

## Features

- Real-time voice conversation with SpotLite (AI set designer persona)
- AI-generated stage mockup images (16:9, based on placeholder or captured stage photo)
- Budget-aware bill of materials with real Indonesian material prices
- Dimension-aware quantity auto-correction (calculates needs based on actual stage size)
- Fuzzy material matching against a 58-item price database
- **Auto-triggered vendor sourcing** for top 3 BOM items (Tokopedia, Shopee, Bukalapak)
- **Location-aware thrift store search** for cheaper secondhand materials
- **Browser geolocation** with auto-detected city (editable by user)
- Budget tracking with color-coded progress bar
- Bento grid layout: stage image, BOM table, vendor panel, chat — all visible at once
- CSV export for the bill of materials
- Conversational iteration ("make it cheaper", "replace the backdrop", "use bamboo instead")
- Gapless audio playback for smooth voice output
- Live camera feed with periodic stage photo updates

---

## Tech Stack

| Layer      | Technology                                                        |
|------------|-------------------------------------------------------------------|
| Backend    | Python 3.11+, FastAPI, uvicorn                                    |
| AI Framework | Google ADK (Agent Development Kit)                              |
| AI Models  | Gemini Live API (native audio), Gemini Image Generation, Gemini Flash (search grounding) |
| Auth       | Vertex AI with Google Cloud Application Default Credentials       |
| Frontend   | Vanilla HTML/JS, Tailwind CSS v4, DaisyUI v5                     |
| Data       | Pre-scraped material prices from juraganmaterial.id (58 items)    |
| Deployment | Docker, Google Cloud Run                                          |

---

## Getting Started

### Prerequisites

- Python 3.11+
- Google Cloud project with billing enabled
- Google Cloud CLI (`gcloud`)

### Setup

```bash
# Clone the repo
git clone <repo-url>
cd spotlite

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Authenticate with Google Cloud
gcloud auth application-default login

# Set up environment variables
cp .env.example .env
# Edit .env with your GCP project ID:
#   GOOGLE_GENAI_USE_VERTEXAI=true
#   GOOGLE_CLOUD_PROJECT=your-project-id
#   GOOGLE_CLOUD_LOCATION=us-central1

# Run locally
uvicorn app.main:app --reload --port 8080

# Open http://localhost:8080
```

### Usage

1. Enter your show name, stage dimensions, budget, and city/region on the setup screen.
2. Click "Start Design Session" to connect to SpotLite.
3. A placeholder stage image is shown. Optionally use the camera button to photograph your real stage.
4. Tap the mic button and describe what you want on stage.
5. SpotLite generates a stage mockup and bill of materials.
6. Vendor results and thrift store suggestions appear automatically in the vendor panel.
7. Iterate by asking for changes — the image, BOM, and vendors update accordingly.
8. Export the final BOM as a CSV file.

---

## Deploy to Cloud Run

**Manual deploy:**
```bash
export GCP_PROJECT_ID=your-project-id
./deploy.sh
```

**Auto-deploy via GitHub:**
Push to `main` triggers Cloud Build automatically via `cloudbuild.yaml`. Set up the trigger with:
```bash
gcloud builds triggers create github --name=spotlite-deploy \
    --repository="projects/YOUR_PROJECT/locations/us-central1/connections/github-connection/repositories/spotlite-repo" \
    --branch-pattern="^main$" --build-config="cloudbuild.yaml" \
    --region=us-central1 --project=YOUR_PROJECT
```

The service runs on Cloud Run with 1Gi memory, 900-second timeout, and session affinity for WebSocket support.

---

## Data Sources

- **Source:** juraganmaterial.id (Indonesian building materials marketplace)
- **Coverage:** 58 items across 10 categories: wood, piping, paint, fabric, fasteners, metal, foam, covering, lighting, tools
- **Storage:** Pre-scraped and stored in `data/materials.json`
- **Matching:** Fuzzy string matching (using Python `difflib.SequenceMatcher`) allows Gemini to request materials by approximate name and still get accurate price lookups

---

## Project Structure

```
spotlite/
  app/
    agent.py             # ADK agent definition, tools, background tasks
    main.py              # FastAPI app, WebSocket endpoint, ADK runner
    prompts.py           # System prompt for SpotLite persona
    prices.py            # Price database loader and BOM generator
    static/
      index.html         # Single-page frontend (bento grid layout)
      app.js             # WebSocket client, audio, camera, vendor panel
      style.css          # Tailwind/DaisyUI custom theme and styles
      stage.png          # Placeholder empty stage image
      logo.png           # SpotLite logo
  data/
    materials.json       # Pre-scraped material prices (58 items)
  Dockerfile             # Container build for Cloud Run
  cloudbuild.yaml        # CI/CD — auto-deploy on push to main
  deploy.sh              # One-command manual Cloud Run deployment
  requirements.txt       # Python dependencies
  .env.example           # Environment variable template
```

---

## Hackathon Track

- **Track:** Live Agents
- **Challenge:** Gemini Live Agent Challenge
- **Required technologies:** Gemini model, Google GenAI SDK, Google Cloud Run

---

## License

MIT
