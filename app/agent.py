# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import datetime
import json
import os
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from dotenv import load_dotenv
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from .a2ui_utils import a2ui_callback

load_dotenv()

# CRITICAL: Hardcode project ID and Cloud Storage bucket as strings.
FIRESTORE_PROJECT = "qwiklabs-gcp-01-5531f6e55bd8"
STORAGE_BUCKET = "wanderlust-travel-assets-5531f6e55bd8"
MEMORY_BANK_ID = "6284903022367604736"

a2ui_schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = a2ui_schema_manager.generate_system_prompt(
    role_description=(
        "You are Wanderlust, an expert AI Travel Concierge. Help travelers discover destinations, "
        "research locations, view details from your Firestore catalog, add new travel recommendations, "
        "check real-time live weather forecasts, convert foreign currency, geocode addresses, search nearby places, "
        "generate visual travel destination images, and run Python code for calculations. Pay special attention to "
        "user allergies (e.g. food, medication, environmental), dietary restrictions, and medical needs. "
        "Always remember all user allergies and preferences across sessions using your PreloadMemoryTool, "
        "and consult these remembered facts whenever providing travel, dining, or itinerary suggestions."
    ),
    workflow_description="Analyze the request, call tools when needed, and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use Table or Heading (unsupported), "
        "or Buttons, actions, or forms (they do nothing in adk web). You may include one Image component, but only when "
        "you have a public https URL for the image (for example the URL an image tool returns after uploading to a public bucket). "
        "Set the Image url to that exact https link, for example {\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. "
        "Never point an Image at a bare filename, an artifact name, or a non-http(s) path. If you do not have a public URL, "
        "add a short Text line noting the image instead. No markdown in text; use the usageHint property ('h1', 'h2', 'body') "
        "for headings and emphasis. Output ONLY the raw A2UI JSON array — no prose, and never wrap it in <a2a_datapart_json> tags "
        "or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


def memory_bank_service_builder():
    return VertexAiMemoryBankService(
        project=FIRESTORE_PROJECT,
        location="us-east1",
        agent_engine_id=MEMORY_BANK_ID,
    )


async def generate_memories_callback(callback_context: CallbackContext):
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        print(f"Note: Memory Bank save skipped: {e}")
    return None


# Read Agent Engine resource name from deployment_metadata.json if available
_deployment_meta_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "deployment_metadata.json"
)
_agent_engine_resource_name = None
if os.path.exists(_deployment_meta_path):
    try:
        with open(_deployment_meta_path, "r") as f:
            _meta = json.load(f)
            _agent_engine_resource_name = _meta.get("remote_agent_runtime_id")
    except Exception as e:
        print(f"Warning: Failed to parse deployment_metadata.json: {e}")

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=_agent_engine_resource_name
)


def _get_firestore_client():
    return firestore.Client(project=FIRESTORE_PROJECT)


def search_destinations(category: str = "", max_budget_usd: int = 0) -> str:
    """Search travel destinations in the Firestore destination catalog.

    Args:
        category: Optional category filter (e.g. 'Beach & Adventure', 'Cultural & Culinary', 'Nature & Adventure').
        max_budget_usd: Optional maximum average daily cost in USD to filter results.

    Returns:
        JSON string containing matching destination entries from Firestore.
    """
    try:
        db = _get_firestore_client()
        docs = db.collection("destinations").stream()
        results = []

        for doc in docs:
            data = doc.to_dict()
            if category and category.lower() not in data.get("category", "").lower():
                continue
            if max_budget_usd > 0 and data.get("average_daily_cost_usd", 0) > max_budget_usd:
                continue
            results.append(data)

        if not results:
            return "No matching destinations found in the catalog."

        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error searching destinations in Firestore: {str(e)}"


def get_destination_details(destination_id: str) -> str:
    """Get full details for a specific travel destination from Firestore.

    Args:
        destination_id: The unique ID of the destination (e.g. 'paris-france', 'kyoto-japan').

    Returns:
        JSON string with destination details or an error message if not found.
    """
    try:
        db = _get_firestore_client()
        doc = db.collection("destinations").document(destination_id).get()

        if not doc.exists:
            return f"Destination with ID '{destination_id}' not found."

        return json.dumps(doc.to_dict(), indent=2)
    except Exception as e:
        return f"Error reading destination '{destination_id}' from Firestore: {str(e)}"


def save_destination(
    destination_id: str,
    name: str,
    country: str,
    tagline: str,
    category: str,
    budget_level: str,
    best_season: str,
    top_attractions: str,
    average_daily_cost_usd: int,
    description: str,
) -> str:
    """Save or update a travel destination entry in the Firestore database.

    Args:
        destination_id: Unique string ID (e.g. 'rome-italy').
        name: Name of the destination (e.g. 'Rome').
        country: Country name (e.g. 'Italy').
        tagline: Catchy tagline summarizing the destination.
        category: Travel category (e.g. 'Cultural & Heritage').
        budget_level: Budget classification (e.g. 'Moderate').
        best_season: Recommended time of year to visit.
        top_attractions: Comma-separated list of top attractions.
        average_daily_cost_usd: Estimated average daily expense in USD.
        description: A brief paragraph describing the location.

    Returns:
        Confirmation message upon successful write to Firestore.
    """
    try:
        db = _get_firestore_client()
        attractions_list = [a.strip() for a in top_attractions.split(",") if a.strip()]

        dest_data = {
            "destination_id": destination_id,
            "name": name,
            "country": country,
            "tagline": tagline,
            "category": category,
            "budget_level": budget_level,
            "best_season": best_season,
            "top_attractions": attractions_list,
            "average_daily_cost_usd": int(average_daily_cost_usd),
            "description": description,
        }

        db.collection("destinations").document(destination_id).set(dest_data)
        return f"Successfully saved destination '{name}' ({destination_id}) to Firestore."
    except Exception as e:
        return f"Error saving destination to Firestore: {str(e)}"


def get_live_weather(location: str) -> str:
    """Fetch live current weather report for any travel destination city worldwide.

    Args:
        location: City name or destination (e.g. 'Paris', 'Kyoto', 'San Francisco', 'Tokyo', 'Reykjavik').

    Returns:
        A string containing real-time live weather condition, temperature, and wind speed.
    """
    try:
        encoded_loc = urllib.parse.quote(location.strip())
        url = f"https://wttr.in/{encoded_loc}?format=%l:+%C,+%t,+wind+%w"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                result = resp.read().decode("utf-8").strip()
                if result:
                    return result
        return f"Unable to fetch live weather for {location}."
    except Exception as e:
        return f"Error fetching live weather for {location}: {str(e)}"


def convert_currency(
    amount: float, from_currency: str = "USD", to_currency: str = "EUR"
) -> str:
    """Convert money between foreign currencies using live central bank exchange rates (Frankfurter API).

    Args:
        amount: The numerical monetary amount to convert (e.g. 150.0).
        from_currency: 3-letter source currency code (e.g. 'USD', 'EUR', 'GBP').
        to_currency: 3-letter target currency code or comma-separated codes (e.g. 'EUR', 'JPY', 'GBP', 'ISK').

    Returns:
        JSON string with converted amounts and live exchange rate details.
    """
    try:
        from_curr = from_currency.strip().upper()
        to_curr = to_currency.strip().upper()
        api_host = os.getenv("CURRENCY_API_HOST", "https://api.frankfurter.app")
        url = f"{api_host}/latest?amount={amount}&from={from_curr}&to={to_curr}"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})

        api_key = os.getenv("CURRENCY_API_KEY")
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")

        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return json.dumps(data, indent=2)

        return f"Unable to convert {amount} {from_curr} to {to_curr}."
    except Exception as e:
        return f"Error converting currency: {str(e)}"


def geocode_address(address: str) -> str:
    """Convert a street address, city name, or landmark into geographic coordinates (latitude and longitude) using Google Geocoding API.

    Args:
        address: The address or place name to geocode (e.g. 'Eiffel Tower, Paris', 'Kyoto Station', 'Rome, Italy').

    Returns:
        JSON string with key fields: name, formatted address, and location (latitude, longitude).
    """
    try:
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not api_key:
            return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

        encoded_address = urllib.parse.quote(address.strip())
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"

        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "OK" and data.get("results"):
                    first_result = data["results"][0]
                    return json.dumps(
                        {
                            "name": address,
                            "address": first_result.get("formatted_address"),
                            "location": first_result.get("geometry", {}).get("location"),
                        },
                        indent=2,
                    )
                return f"Geocoding failed for '{address}': {data.get('status')}"
        return f"Geocoding request failed with HTTP status {resp.status}."
    except Exception as e:
        return f"Error geocoding address: {str(e)}"


def search_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "tourist_attraction",
    radius_meters: float = 1000.0,
) -> str:
    """Find nearby places (attractions, restaurants, hotels) around coordinates using Google Places API (New).

    Args:
        latitude: Latitude of the center point (e.g. 48.8566).
        longitude: Longitude of the center point (e.g. 2.3522).
        place_type: Type of place to search (e.g. 'tourist_attraction', 'restaurant', 'cafe', 'museum', 'lodging').
        radius_meters: Search radius in meters (default: 1000.0).

    Returns:
        JSON string containing list of nearby places with key fields: name, address, and location (latitude, longitude).
    """
    try:
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not api_key:
            return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

        url = "https://places.googleapis.com/v1/places:searchNearby"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
        }

        body = {
            "includedTypes": [place_type.strip().lower()],
            "maxResultCount": 5,
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": float(latitude),
                        "longitude": float(longitude),
                    },
                    "radius": float(radius_meters),
                }
            },
        }

        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                places = data.get("places", [])
                formatted_places = []
                for p in places:
                    formatted_places.append(
                        {
                            "name": p.get("displayName", {}).get("text"),
                            "address": p.get("formattedAddress"),
                            "location": p.get("location"),
                        }
                    )
                return json.dumps(formatted_places, indent=2)
        return f"Places search failed with HTTP status {resp.status}."
    except Exception as e:
        return f"Error searching nearby places: {str(e)}"


async def generate_destination_image(
    prompt: str, tool_context: ToolContext
) -> str:
    """Generate a visual travel image using gemini-3.1-flash-lite-image model in global region.

    Saves the image as an ADK artifact (Playground Artifacts panel) and uploads it to public Cloud Storage bucket,
    returning its public HTTPS URL.

    Args:
        prompt: Detailed image generation prompt describing the travel destination scene.

    Returns:
        Public HTTPS URL string (https://storage.googleapis.com/<bucket>/<filename>).
    """
    try:
        client = genai.Client(
            vertexai=True, project=FIRESTORE_PROJECT, location="global"
        )

        resp = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        image_bytes = None
        if resp.candidates and resp.candidates[0].content:
            for part in resp.candidates[0].content.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    break

        if not image_bytes:
            return "Error: gemini-3.1-flash-lite-image model did not return image bytes."

        filename = f"destination_image_{int(time.time())}.png"

        # (1) Save image as ADK artifact so it appears in Playground Artifacts panel
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
        await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # (2) Upload image bytes to public Cloud Storage bucket and return public HTTPS URL
        storage_client = storage.Client(project=FIRESTORE_PROJECT)
        bucket = storage_client.bucket(STORAGE_BUCKET)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type="image/png")

        public_url = f"https://storage.googleapis.com/{STORAGE_BUCKET}/{filename}"
        return public_url
    except Exception as e:
        return f"Error generating destination image: {str(e)}"


async def generate_destination_video(
    prompt: str, tool_context: ToolContext
) -> str:
    """Generate a short video clip for a travel destination or item using gemini-omni-flash-preview model in global region.

    Saves the video as an ADK artifact (Playground Artifacts panel) and uploads it to public Cloud Storage bucket,
    returning its public HTTPS URL.

    Args:
        prompt: Detailed video generation prompt describing the travel destination or item scene.

    Returns:
        Public HTTPS URL string (https://storage.googleapis.com/<bucket>/<filename>).
    """
    try:
        client = genai.Client(
            vertexai=True, project=FIRESTORE_PROJECT, location="global"
        )

        interaction = client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt,
        )

        video_data = getattr(getattr(interaction, "output_video", None), "data", None)
        if not video_data:
            return "Error: gemini-omni-flash-preview model did not return video output."

        if isinstance(video_data, bytes):
            video_bytes = video_data
        elif isinstance(video_data, str):
            video_bytes = base64.b64decode(video_data)
        else:
            return "Error: Unexpected video data format returned from gemini-omni-flash-preview."

        filename = f"destination_video_{int(time.time())}.mp4"

        # (1) Save video as ADK artifact so it appears in Playground Artifacts panel
        artifact_part = types.Part.from_bytes(data=video_bytes, mime_type="video/mp4")
        await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # (2) Upload video bytes directly to public Cloud Storage bucket (without writing to local file)
        storage_client = storage.Client(project=FIRESTORE_PROJECT)
        bucket = storage_client.bucket(STORAGE_BUCKET)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type="video/mp4")

        public_url = f"https://storage.googleapis.com/{STORAGE_BUCKET}/{filename}"
        return public_url
    except Exception as e:
        return f"Error generating destination video: {str(e)}"


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        vertexai=True,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=code_executor,
    instruction=a2ui_instruction,
    tools=[
        search_destinations,
        get_destination_details,
        save_destination,
        get_live_weather,
        convert_currency,
        geocode_address,
        search_nearby_places,
        generate_destination_image,
        generate_destination_video,
        PreloadMemoryTool(),
        get_current_time,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
