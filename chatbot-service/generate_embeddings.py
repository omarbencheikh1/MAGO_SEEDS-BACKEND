import os
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

# 1. Connect to MongoDB
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("MONGO_URI is missing from your .env file!")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client.get_default_database()
products_collection = db["products"]

# 2. Load Free Local Embedding Model
print("Loading local embedding model (all-MiniLM-L6-v2)...")
model = SentenceTransformer("all-MiniLM-L6-v2")

# 3. Retrieve all products
products = list(products_collection.find({}))
print(f"Found {len(products)} products to process.")

# 4. Generate vectors and update documents
for p in products:
    # 4a. Flatten your nested 'specifications' array of objects (e.g. [{"label": "Shape", "value": "Bottle"}]) [1.1.2]
    specs_list = []
    specifications = p.get("specifications", [])
    for spec in specifications:
        label = spec.get("label", "")
        value = spec.get("value", "")
        if label and value:
            specs_list.append(f"{label}: {value}")
    specs_text = ". ".join(specs_list)

    # 4b. Map ALL descriptive schema fields into the text block [1.1.2, 1.2.6]
    text_parts = [
        f"Name: {p.get('name', '')}",
        f"Category: {p.get('category', '')}",
        f"SKU: {p.get('sku', '')}",
        f"Weight: {p.get('weight', '')}",
        f"Origin: {p.get('origin', '')}",
        f"Harvest Period: {p.get('harvestPeriod', '')}",
        f"Sowing Period: {p.get('sowingPeriod', '')}",
        f"Germination: {p.get('germination', '')}",
        f"Culture Tips: {p.get('cultureTips', '')}",
        f"Description: {p.get('description', '')}",
        f"Short Description: {p.get('shortDescription', '')}",
        f"Content: {p.get('content', '')}",
        f"Type: {p.get('type', 'none')}"
    ]
    
    # Append flattened specifications if they exist [1.1.2]
    if specs_text:
        text_parts.append(f"Specifications: {specs_text}")
        
    # Combine everything into one massive rich text string, removing empty fields [1.1.2]
    text_to_embed = ". ".join([part for part in text_parts if part.strip()])
    
    # 4c. Generate the 384-dimensional vector
    vector = model.encode(text_to_embed).tolist()
    
    # 4d. Save the vector back to MongoDB
    products_collection.update_one(
        {"_id": p["_id"]},
        {"$set": {"embedding": vector}}
    )
    print(f"Embedded: {p.get('name')} (Indexed fields: {len(text_parts)})")

print("\nAll products successfully embedded in MongoDB utilizing all schema fields!")