# Stage Buddy - Design Document

**Date:** 2026-03-14
**Track:** Live Agents
**Hackathon:** Gemini Live Agent Challenge (deadline: March 16, 2026 5:00 PM PT)
**Team:** 2 developers, 1 product person

## Problem

Musical theater in Indonesia faces a massive disconnect between production costs and market demand. Student communities and indie productions often go bankrupt ("boncos") because the vendor ecosystem is monopolized by high-priced concert prop makers. Directors lack tools to plan sets within budget, and have no data to negotiate fair prices with vendors.

## Solution

A web app where theater directors photograph an empty stage, then have a real-time voice conversation with Gemini to design the set within a budget. Gemini generates updated stage mockup images and an itemized bill of materials with real Indonesian material prices.

## Core User Flow

1. Director opens app, enters: show name, stage dimensions (W x D x H meters), budget (IDR)
2. Taps "Capture Stage" to photograph the empty venue via phone/laptop camera
3. Starts a voice conversation with Gemini Live
4. Speaks: "I want a tropical beach theme with a main platform center stage, two palm trees on each side, and a painted ocean backdrop"
5. Gemini responds with voice + triggers:
   - Stage mockup image (original photo with elements composited in)
   - Bill of materials with real IDR prices from pre-scraped database
   - Running budget tracker
6. Director iterates: "That's too expensive, replace the wooden platform with stacked pallets"
7. Gemini updates image + BOM + budget
8. Director exports final BOM as PDF/CSV

## Architecture

```
Browser (Frontend)
  - Camera capture (getUserMedia)
  - Mic/Speaker (WebAudio API, PCM 16kHz)
  - Stage View (generated image)
  - BOM table + budget bar
  - WebSocket connection to backend
       |
       | WebSocket (audio stream, photos, results)
       |
FastAPI Backend (Cloud Run)
  - Gemini Live Session Manager
    - Persistent async connection to gemini-live-2.5-flash-preview
    - System instruction with role, budget, dimensions, price data summary
    - Sends: audio chunks + stage photo
    - Receives: audio response + function calls
  - Function Handlers
    - generate_stage_image(description, stage_photo) -> Gemini Image API
    - generate_bom(items[]) -> price DB lookup + formatting
  - Price Database
    - JSON file loaded at startup
    - Pre-scraped from juraganmaterial.id
```

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, uvicorn, google-genai SDK
- **Frontend:** Vanilla HTML/JS/CSS (no framework)
- **Deployment:** Docker -> Google Cloud Run
- **Data:** Pre-scraped material prices (JSON)
- **Scraping:** Firecrawl or ScrapegraphAI (offline CLI script)

## WebSocket Message Protocol

```
Client -> Server:
  { type: "audio", data: <base64 PCM chunk> }
  { type: "photo", data: <base64 JPEG> }
  { type: "start_session", config: { name, width, depth, height, budget } }

Server -> Client:
  { type: "audio", data: <base64 PCM chunk> }
  { type: "transcript", role: "user"|"assistant", text: "..." }
  { type: "stage_image", data: <base64 image> }
  { type: "bom", items: [...], total: number, budget: number }
```

## UI Layout (Main Session Screen)

```
+-------------------------+--------------------------+
|                         |                          |
|     Stage View          |    Conversation Panel    |
|  (generated image)      |    Voice status          |
|                         |    Transcript log        |
|  [Capture Stage btn]    |    [Hold to Talk btn]    |
|                         |                          |
+-------------------------+--------------------------+
|                                                    |
|  Bill of Materials table                           |
|  Item | Qty | Material | Unit Price | Total        |
|                                                    |
|  Budget: Rp X / Rp Y  [progress bar]  [Export PDF] |
+----------------------------------------------------+
```

## Price Database Schema

```json
[
  {
    "name": "Pipa PVC 3/4 inch",
    "category": "piping",
    "unit": "per batang (4m)",
    "price_idr": 35000,
    "source": "juraganmaterial.id",
    "scraped_at": "2026-03-14"
  }
]
```

Source: juraganmaterial.id (pre-scraped, ~50-100 items covering wood, PVC, paint, fabric, nails, tools)
Scraping script: scripts/scrape_prices.py (committed to repo, runs offline)

## Gemini Function Declarations

### generate_stage_image
- **Trigger:** When Gemini has enough context to visualize the set
- **Params:** description (string), elements (list of stage elements with positions)
- **Action:** Backend calls Gemini image generation API with the original stage photo + description
- **Returns:** Base64 image pushed to frontend

### generate_bom
- **Trigger:** When Gemini has identified materials needed
- **Params:** items (list of {name, category, quantity, material_type})
- **Action:** Backend fuzzy-matches items against price database, calculates totals
- **Returns:** Structured BOM JSON pushed to frontend

## Track Compliance: Live Agents

- Uses Gemini Live API for real-time bidirectional audio streaming
- Supports natural interruption handling (director can interrupt mid-response)
- Distinct persona: veteran theatrical set designer who is budget-conscious
- Multimodal input: voice + camera photo
- Real-time output: voice + generated images + structured data

## Hackathon Compliance Checklist

- [ ] All code written during contest period (Feb 16 - Mar 16, 2026)
- [ ] Public GitHub repo with README (setup instructions, API keys, deployment)
- [ ] Architecture diagram included in submission
- [ ] Demo video < 4 minutes, public on YouTube, English, real software
- [ ] Separate screen recording of Cloud Run deployment proof
- [ ] juraganmaterial.id disclosed as third-party data source
- [ ] Cloud Run service stays live through April 3, 2026
- [ ] Submission text covers: features, technologies, data sources, learnings

## Bonus Points

- [ ] Blog post/video about build process with #GeminiLiveAgentChallenge (+0.6)
- [ ] Dockerfile + deployment script in repo (+0.2)
- [ ] Team member joins Google Developer Group (+0.2)

## Features NOT Building

- Augmented Reality
- 3D scene (three.js)
- Local artisan matchmaking
- Spatial constraint calculation
- Live price scraping during session
- Tokopedia scraping
