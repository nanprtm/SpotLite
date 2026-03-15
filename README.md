# Stage Buddy

**Voice-powered stage design assistant for Indonesian theater**

Stage Buddy is a web application that helps theater directors design stage sets through real-time voice conversation with an AI set designer. Directors describe their vision aloud and receive AI-generated mockup images along with an itemized bill of materials using real Indonesian building material prices — all within a specified budget.

---

## Problem Statement

Musical theater in Indonesia faces a massive disconnect between production costs and market demand. Student communities and indie productions often go bankrupt ("boncos") because the vendor ecosystem is monopolized by high-priced concert prop makers. Directors lack tools to plan sets within budget and have no data to negotiate fair prices with vendors. There is no accessible way to visualize a design, estimate costs, and iterate on both simultaneously.

## Solution

Stage Buddy is a web app where theater directors have a real-time voice conversation with Gemini to design their set within a budget. The AI persona "Teman Panggung" (Stage Buddy) acts as an energetic, creative set designer who understands local materials, costs, and creative workarounds. Gemini generates updated stage mockup images and an itemized bill of materials with real Indonesian material prices sourced from juraganmaterial.id. Directors can iterate conversationally — asking to make things cheaper, swap materials, or redesign sections — and see both the visual and cost impact in real time.

---

## Architecture

```
+---------------------------------------------------+
|                    Browser                         |
|  Camera + Mic -> WebSocket -> Stage View + BOM    |
+------------------------+--------------------------+
                         | WebSocket (audio, photos, results)
+------------------------v--------------------------+
|            FastAPI Backend (Cloud Run)              |
|                                                    |
|  Gemini Live API <-> Session Manager               |
|        | function calls                            |
|  Image Generation (Gemini) + BOM Generator         |
|        |                                           |
|  Price Database (pre-scraped from                  |
|  juraganmaterial.id)                               |
+----------------------------------------------------+
```

**Key technical details:**

- **Live API model:** `gemini-live-2.5-flash-native-audio` (GA) for real-time voice streaming
- **Image model:** `gemini-2.5-flash-image` with 16:9 aspect ratio
- **Auth:** Vertex AI with Google Cloud credentials (not API key)
- **Session management:** Live API sessions naturally end after each turn. Context is preserved via conversation history and injected into the system instruction on reconnect, providing seamless continuity.
- **Image generation:** Runs in background to avoid blocking the Live session. Includes retry with backoff on rate limits and a queue guard to prevent duplicate generations.
- **Audio playback:** Gapless scheduling via Web Audio API `source.start(nextPlayTime)` for smooth voice output.

**Data flow:**

1. The director opens the app, enters show details (name, stage dimensions, budget), and starts a session.
2. A WebSocket connection is established to the FastAPI backend.
3. A placeholder stage image is displayed. The director can optionally capture their real stage via camera.
4. The director taps the mic and describes what they want on stage.
5. Teman Panggung repeats back the request to confirm alignment, then generates the visualization.
6. Gemini triggers function calls:
   - `generate_stage_image` — calls the Gemini image model to produce a stage mockup based on the placeholder or captured stage photo.
   - `generate_bom` — matches requested materials against the price database using fuzzy matching and returns an itemized cost breakdown with dimension-aware quantity estimates.
7. Results (audio response, generated images, BOM data) are streamed back to the browser.
8. The frontend renders the stage mockup, updates the BOM table, and shows budget utilization on a progress bar.

---

## Features

- Real-time voice conversation with "Teman Panggung" (AI set designer persona)
- AI-generated stage mockup images (16:9, based on placeholder or captured stage photo)
- Budget-aware bill of materials with real Indonesian material prices
- Dimension-aware quantity estimation (calculates material needs based on actual stage size)
- Fuzzy material matching against a 58-item price database
- Budget tracking with visual progress bar (color-coded warnings)
- CSV export for the bill of materials
- Conversational iteration ("make it cheaper", "replace the backdrop", "use bamboo instead")
- Confirm-before-generate interaction flow (agent repeats back the request before generating)
- Image generation queue guard (prevents duplicate/overlapping generations)
- Session continuity across Live API reconnects via conversation history
- Gapless audio playback for smooth voice output
- Debug conversation logs in `logs/` directory

---

## Tech Stack

| Layer      | Technology                                                        |
|------------|-------------------------------------------------------------------|
| Backend    | Python 3.11+, FastAPI, uvicorn                                    |
| AI         | Google GenAI SDK, Gemini Live API (native audio), Gemini Image Generation |
| Auth       | Vertex AI with Google Cloud Application Default Credentials       |
| Frontend   | Vanilla HTML, JavaScript, CSS (no frameworks)                     |
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
cd stage-buddy

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

1. Enter your show name, stage dimensions, and budget on the setup screen.
2. Click "Start Design Session" to connect to the AI.
3. A placeholder stage image is shown. Optionally use "Capture Stage" to photograph your real stage.
4. Tap the Mic button and describe what you want on stage.
5. Teman Panggung will repeat your request for confirmation, then generate a stage mockup and bill of materials.
6. Iterate by asking for changes — the image and BOM update in real time.
7. Export the final BOM as a CSV file.

---

## Deploy to Cloud Run

```bash
export GCP_PROJECT_ID=your-project-id
./deploy.sh
```

The deploy script builds a Docker container, pushes it to Google Container Registry, and deploys to Cloud Run. The service is configured with 512Mi memory and a 300-second timeout to accommodate long voice sessions.

---

## Data Sources

- **Source:** juraganmaterial.id (Indonesian building materials marketplace)
- **Coverage:** 58 items across 10 categories: wood, piping, paint, fabric, fasteners, metal, foam, covering, lighting, tools
- **Storage:** Pre-scraped and stored in `data/materials.json`
- **Scraping script:** `scripts/scrape_prices.py`
- **Matching:** Fuzzy string matching (using Python `difflib.SequenceMatcher`) allows Gemini to request materials by approximate name and still get accurate price lookups

---

## Project Structure

```
stage-buddy/
  app/
    main.py              # FastAPI app, WebSocket endpoint, routes
    gemini_session.py    # Gemini Live session manager with function calling
    prompts.py           # System prompt for the Teman Panggung persona
    prices.py            # Price database loader and BOM generator
    static/
      index.html         # Single-page frontend
      app.js             # WebSocket client, audio capture/playback, UI logic
      style.css          # Styles
      stage.png          # Placeholder empty stage image
  data/
    materials.json       # Pre-scraped material prices (58 items)
  logs/                  # Debug conversation logs (gitignored)
  scripts/
    scrape_prices.py     # Price scraping/population script
  tests/
    test_prices.py       # Unit tests for price matching and BOM generation
  Dockerfile             # Container build for Cloud Run
  deploy.sh              # One-command Cloud Run deployment
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
