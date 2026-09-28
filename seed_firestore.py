import os
from google.cloud import firestore

# CRITICAL: Hardcode the project ID as a string.
# On Agent Platform, GOOGLE_CLOUD_PROJECT returns the project NUMBER, which breaks Firestore.
FIRESTORE_PROJECT = "qwiklabs-gcp-01-5531f6e55bd8"

DESTINATIONS = [
    {
        "destination_id": "paris-france",
        "name": "Paris",
        "country": "France",
        "tagline": "The City of Light, romance, and iconic art",
        "category": "Cultural & Culinary",
        "budget_level": "Moderate-Luxury",
        "best_season": "Spring (April–June) or Autumn (Sept–Nov)",
        "top_attractions": ["Eiffel Tower", "Louvre Museum", "Montmartre", "Notre-Dame"],
        "average_daily_cost_usd": 250,
        "description": "Explore world-class museums, charming sidewalk cafes, and timeless Gothic architecture along the Seine.",
    },
    {
        "destination_id": "kyoto-japan",
        "name": "Kyoto",
        "country": "Japan",
        "tagline": "Japan's cultural heart filled with ancient temples and bamboo groves",
        "category": "Cultural & Heritage",
        "budget_level": "Moderate",
        "best_season": "Spring (Cherry Blossoms) or Autumn (Fall Foliage)",
        "top_attractions": ["Fushimi Inari Shrine", "Arashiyama Bamboo Grove", "Kinkaku-ji (Golden Pavilion)", "Gion District"],
        "average_daily_cost_usd": 180,
        "description": "Experience serene zen gardens, traditional tea houses, historic wooden architecture, and seasonal beauty.",
    },
    {
        "destination_id": "maui-hawaii",
        "name": "Maui",
        "country": "United States",
        "tagline": "The Valley Isle of pristine beaches and dramatic volcanic landscapes",
        "category": "Beach & Adventure",
        "budget_level": "Luxury",
        "best_season": "Year-round (Dec–April for whale watching)",
        "top_attractions": ["Road to Hana", "Haleakala National Park", "Kaanapali Beach", "Molokini Crater"],
        "average_daily_cost_usd": 350,
        "description": "Discover scenic coastal drives, world-class snorkeling, lush rainforest waterfalls, and stunning Pacific sunsets.",
    },
    {
        "destination_id": "barcelona-spain",
        "name": "Barcelona",
        "country": "Spain",
        "tagline": "Vibrant Catalan capital famous for Gaudí architecture and tapas culture",
        "category": "Architectural & Beach",
        "budget_level": "Moderate",
        "best_season": "May–June or September–October",
        "top_attractions": ["Sagrada Família", "Park Güell", "Gothic Quarter", "Barceloneta Beach"],
        "average_daily_cost_usd": 170,
        "description": "Immerse yourself in whimsical modernist architecture, lively seaside promenades, and bustling tapas markets.",
    },
    {
        "destination_id": "reykjavik-iceland",
        "name": "Reykjavik",
        "country": "Iceland",
        "tagline": "Gateway to geothermal wonders and northern lights",
        "category": "Nature & Adventure",
        "budget_level": "Luxury",
        "best_season": "Sept–March for Northern Lights, June–August for Midnight Sun",
        "top_attractions": ["Blue Lagoon", "Golden Circle", "Hallgrímskirkja", "Black Sand Beach (Reynisfjara)"],
        "average_daily_cost_usd": 280,
        "description": "Witness roaring waterfalls, bubbling geysers, dramatic volcanic landscapes, and rejuvenating geothermal spas.",
    }
]


def seed():
    print(f"Connecting to Firestore for project: {FIRESTORE_PROJECT}...")
    db = firestore.Client(project=FIRESTORE_PROJECT)
    collection_ref = db.collection("destinations")

    for dest in DESTINATIONS:
        doc_ref = collection_ref.document(dest["destination_id"])
        doc_ref.set(dest)
        print(f"Seeded destination: {dest['name']} ({dest['destination_id']})")

    print("\n✅ Successfully seeded Firestore catalog!")


if __name__ == "__main__":
    seed()
