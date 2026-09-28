# Wanderlust AI Travel Concierge

![Wanderlust AI Agent Demo](demo.gif)

**Wanderlust** is an intelligent, multi-tool AI travel concierge agent built with the **Google Agent Development Kit (ADK)**, **Gemini 2.5 Flash**, **Vertex AI Memory Bank**, and **A2UI (Agent-to-User Interface)**. It assists travelers in discovering destinations, researching itinerary recommendations, managing a Firestore travel catalog, fetching live weather and exchange rates, geocoding landmarks, finding nearby attractions, and generating custom AI images and video previews.

---

## 🚀 Implemented Capabilities & Architecture

Based strictly on the codebase in `app/agent.py` and `agents-cli-manifest.yaml`, the following services and tools are fully implemented and integrated:

### ☁️ Google Cloud Services & Vertex AI
* **Vertex AI Memory Bank Service**: Uses `VertexAiMemoryBankService` with `PreloadMemoryTool` and an `after_agent_callback` to persist user facts (allergies, dietary restrictions, preferred budget, travel styles) across sessions.
* **Google Cloud Firestore Database**: Manages the destination catalog with live database searches (`search_destinations`), detail lookups (`get_destination_details`), and entry updates (`save_destination`).
* **Google Cloud Storage (GCS)**: Stores generated travel media assets (AI postcard images and video previews) in a public GCS bucket.
* **Vertex AI Gemini Models**:
  * `gemini-2.5-flash`: Core conversation engine and tool calling agent.
  * `gemini-3.1-flash-lite-image` (Global Region): Generates visual travel destination images and postcards (`generate_destination_image`).
  * `gemini-omni-flash-preview` (Global Region): Generates short travel video clips (`generate_destination_video`).
* **Agent Engine Sandbox Code Executor**: Runs Python code execution in a secure sandboxed environment via `AgentEngineSandboxCodeExecutor`.

### 🎨 Agent-to-User Interface (A2UI)
* **A2UI Schema Manager & Callback**: Automatically formats travel responses, itinerary plans, and destination cards into structured A2UI surfaces (`Card`, `Column`, `Row`, `Text`, `Image`).
* **Custom Frontend Renderer**: Built-in FastAPI proxy and glassmorphism web UI to render A2UI cards natively in the browser.

### 🛠️ Function Tools & External APIs
1. **Firestore Destination Search** (`search_destinations`): Filter destination catalog by category and daily budget limit.
2. **Firestore Destination Details** (`get_destination_details`): Fetch complete metadata for a specific travel location.
3. **Firestore Save Destination** (`save_destination`): Save or update destination records in Firestore.
4. **Live Weather Report** (`get_live_weather`): Real-time weather conditions, temperature, and wind speed via wttr.in.
5. **Live Currency Exchange** (`convert_currency`): Foreign currency conversions using central bank exchange rates via Frankfurter API.
6. **Google Geocoding API** (`geocode_address`): Resolves addresses and place names into geographic coordinates.
7. **Google Places API (New)** (`search_nearby_places`): Discovers nearby attractions, restaurants, cafes, and lodging around coordinates.
8. **AI Image Generation** (`generate_destination_image`): Saves generated images as ADK artifacts and uploads to Cloud Storage.
9. **AI Video Generation** (`generate_destination_video`): Saves generated video bytes as ADK artifacts and uploads to Cloud Storage.
10. **Preload Memory Tool** (`PreloadMemoryTool`): Automatically injects remembered user preferences into conversation context.

---

## 📌 Planned / Future Features

The following features were outlined in initial design concepts but are **planned, not yet implemented**:
* **Static Google Maps Image Embedding**: *Planned, not yet implemented.*
* **Multi-Agent Booking Subagents**: *Planned, not yet implemented.*

---

## 📁 Repository Structure

```
wanderlust-concierge/
├── app/
│   ├── agent.py               # Main ADK agent definition & tool functions
│   ├── a2ui_utils.py          # A2UI model callback & component catalog
│   └── fast_api_app.py        # ADK FastAPI service entrypoint
├── frontend/
│   ├── main.py                # FastAPI proxy server (A2A protocol & static files)
│   └── static/
│       └── index.html         # Custom glassmorphism UI & A2UI web renderer
├── scratch/                   # Demo recording & synthesis utilities
├── seed_firestore.py          # Script to seed initial destination catalog into Firestore
├── agents-cli-manifest.yaml   # Agent Engine deployment manifest
├── pyproject.toml             # Project dependencies and environment specs
└── demo.gif                   # Looping recorded demo of the agent
```

---

## 🛠️ Local Setup & Run Instructions

### Prerequisites
* **Python 3.10+** installed.
* **uv** package manager installed (`uv pip` or `uv sync`).
* **Google Cloud SDK (`gcloud`)** authenticated with active project permissions.

### 1. Installation & Environment Configuration
Clone the repository and set up environment variables:

```bash
# Set up virtual environment & dependencies
uv sync

# Configure environment variables
cp .env.example .env
```

Ensure your `.env` file contains your GCP configuration and optional Maps API key:

```env
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_REGION=us-east1
GOOGLE_MAPS_API_KEY=your-maps-api-key
```

### 2. Seed Firestore Catalog
Seed the initial travel destination database:

```bash
uv run python seed_firestore.py
```

### 3. Run Agent Development Server

To run the standard ADK Developer UI Playground:

```bash
agents-cli playground
```

To run the custom FastAPI Proxy & Glassmorphism Web Interface:

```bash
uv run python frontend/main.py
```

Open your browser to the local server address displayed in the terminal output to start chatting with your Wanderlust AI Concierge!
