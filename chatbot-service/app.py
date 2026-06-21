import os
import re
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from bson import ObjectId
from groq import Groq
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# Load Python specific environment variables
load_dotenv()

app = FastAPI()

# Initialize MongoDB Connection
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    print("WARNING: MONGO_URI is not set. Check your chatbot-service/.env file.")
else:
    try:
        mongo_client = MongoClient(MONGO_URI)
        db = mongo_client.get_default_database()
        products_collection = db["products"]
        reviews_collection = db["reviews"]
        print("Connected to MongoDB successfully!")
    except Exception as e:
        print(f"MongoDB Connection Error: {e}")

# Initialize Groq Client securely from environment variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("ERROR: GROQ_API_KEY is missing!")

groq_client = Groq(api_key=GROQ_API_KEY)

# Initialize local Free Embedding Model
print("Loading local vector embedding model (all-MiniLM-L6-v2)...")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


class ChatRequest(BaseModel):
    message: str
    history: list = []


class EmbedRequest(BaseModel):
    product_id: str


class RelatedRequest(BaseModel):
    product_id: str


def serialize_mongo_data(data):
    """
    Recursively converts all ObjectId instances in lists/dictionaries to strings
    to prevent FastAPI's jsonable_encoder from crashing on BSON types.
    """
    if isinstance(data, list):
        return [serialize_mongo_data(item) for item in data]
    elif isinstance(data, dict):
        return {k: serialize_mongo_data(v) for k, v in data.items()}
    elif isinstance(data, ObjectId):
        return str(data)
    else:
        return data


def is_simple_greeting(user_query: str) -> bool:
    """
    Detects if the user's message is a simple greeting (e.g. 'hello', 'hi', 'marhaba')
    so we can avoid triggering the 'no products found' database warning.
    """
    q = user_query.lower().strip().strip("?!.🌿")
    greetings = {
        "hello", "hi", "hey", "marhaba", "salam", "bonjour", 
        "salam alaykoum", "aslema", "aslema marhaba", "ahlan"
    }
    return q in greetings


def should_force_all_products(user_query: str) -> bool:
    """
    Heuristics: Instantly detects if the query is a catalog-wide comparative question.
    """
    q = user_query.lower()
    trigger_words = [
        "priciest", "cheapest", "expensive", "costly", "pricey", "cheap", "price", "low", "high",
        "catalog", "all products", "everything you have", "what do you sell",
        "show me your seeds", "full list", "entire store", "what do you carry"
    ]
    return any(word in q for word in trigger_words)


def extract_search_intent(user_query: str, history: list) -> dict:
    """
    Global NLU Parser: Uses Groq to convert conversational user messages 
    into structured JSON parameters: {"keyword": str, "origin": str}.
    This completely eliminates the need for hardcoded country lists.
    """
    formatted_history = ""
    for msg in history[-5:-1]:
        role = "User" if not msg.get("isBot") else "Assistant"
        formatted_history += f"{role}: {msg.get('text')}\n"

    prompt = (
        "You are an NLU search parser for a seed shop. Analyze the user's latest message and conversation history, "
        "and output a JSON object with exactly two keys: 'keyword' and 'origin'.\n\n"
        
        "RULES:\n"
        "1. 'keyword': Extract the core plant/seed name the user is interested in. "
        "If they ask a follow-up about a product discussed in the history, return that product's name (e.g., 'brad's atomic grape'). "
        "If they ask a comparative question about the entire catalog (e.g., 'priciest', 'cheapest', 'what do you carry'), return 'all'. "
        "If no specific plant is asked, return 'none'.\n"
        
        "2. 'origin': Extract any geographic, national, or regional origin the user asks for. "
        "Normalize nationalities/adjectives to the actual country name (e.g., 'french' -> 'france', 'american' -> 'united states', "
        "'italian' -> 'italy', 'tunisian' -> 'tunisia', 'danish' -> 'denmark', 'swiss' -> 'switzerland'). "
        "If no geographic origin is mentioned, return 'none'.\n\n"
        
        "Examples:\n"
        "- 'what are the products from french origin?' -> {\"keyword\": \"none\", \"origin\": \"france\"}\n"
        "- 'what are the tunisian pepper varieties?' -> {\"keyword\": \"pepper\", \"origin\": \"tunisia\"}\n"
        "- 'any beets from denmark?' -> {\"keyword\": \"beets\", \"origin\": \"denmark\"}\n"
        "- 'show me the cheapest seeds from italy' -> {\"keyword\": \"all\", \"origin\": \"italy\"}\n\n"
        
        f"Conversation History:\n{formatted_history}\n"
        f"Latest User Message: '{user_query}'\n\n"
        "Output ONLY the raw JSON block. Do not include markdown code block formatting (```json), no explanations, and no extra text."
    )
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=100
        )
        raw_output = completion.choices[0].message.content.strip()
        
        # Clean any accidental markdown block formatting before parsing JSON
        raw_output = re.sub(r'```json\s*|```\s*', '', raw_output).strip()
        data = json.loads(raw_output)
        
        return {
            "keyword": data.get("keyword", "none").strip().lower(),
            "origin": data.get("origin", "none").strip().lower()
        }
    except Exception as e:
        print(f"NLU Intent Parser failed: {e}. Falling back to defaults.")
        return {"keyword": "none", "origin": "none"}


def search_local_products_vector(search_keyword: str, origin_country: str, user_query: str, force_all: bool = False):
    """
    Advanced Multi-Attribute Search.
    Fuses database filters (price, country) with lexical and vector searches.
    """
    if not force_all and search_keyword == "none" and origin_country == "none":
        return []

    # 1. Determine sorting logic based on intent
    sort_field = None
    sort_direction = 1
    
    q_lower = user_query.lower()
    if any(word in q_lower for word in ["priciest", "expensive", "costly", "pricey", "highest"]):
        sort_field = "numeric_price"
        sort_direction = -1
    elif any(word in q_lower for word in ["cheapest", "lowest", "affordable", "least expensive", "cheapeast"]):
        sort_field = "numeric_price"
        sort_direction = 1

    # 2. Build geographic query dynamically and globally
    geo_query = {}
    if origin_country != "none":
        # Atlas mapping rule: group US abbreviations together
        if origin_country in ["united states", "usa", "us", "america"]:
            geo_query = {"origin": {"$regex": "united states|usa", "$options": "i"}}
        else:
            geo_query = {"origin": {"$regex": origin_country, "$options": "i"}}

    # 3. Build lexical match stage
    if search_keyword == "all" or search_keyword == "none":
        match_stage = {}
    else:
        tokens = search_keyword.split()
        token_queries = []
        for token in tokens:
            token_clean = token.strip()
            if not token_clean:
                continue
            if len(token_clean) <= 2 and token_clean in ["in", "is", "of", "the", "for", "and", "or", "to", "at", "by", "de"]:
                continue
            token_regex = {"$regex": token_clean, "$options": "i"}
            token_queries.append({
                "$or": [
                    {"name": token_regex},
                    {"category": token_regex},
                    {"description": token_regex}
                ]
            })
        
        if token_queries:
            match_stage = {"$and": token_queries}
        else:
            match_stage = {}

    # 4. Fuse Lexical Match with Geographic Filters
    if geo_query:
        if match_stage:
            match_stage = {"$and": [geo_query, match_stage]}
        else:
            match_stage = geo_query

    pipeline = []
    
    # Case A: Comparative, Geographic, or Keyword Query (Uses deterministic database logic)
    if force_all or geo_query or (match_stage and search_keyword != "none"):
        if match_stage:
            pipeline.append({"$match": match_stage})
        pipeline.append({
            "$addFields": {
                "numeric_price": {
                    "$convert": {
                        "input": "$price",
                        "to": "double",
                        "onError": 0.0,
                        "onNull": 0.0
                    }
                }
            }
        })
        if sort_field:
            pipeline.append({"$sort": {sort_field: sort_direction}})
        pipeline.append({"$limit": 15})
        
    # Case B: Semantic Query (Uses Vector Search)
    else:
        query_vector = embedding_model.encode(search_keyword).tolist()
        
        # Setup vector search parameters
        vector_search_stage = {
            "index": "vector_index",
            "path": "embedding",
            "queryVector": query_vector,
            "numCandidates": 100,
            "limit": 15
        }
        
        # If there is a geographic origin request, include it inside the vector search filter option
        if geo_query:
            vector_search_stage["filter"] = geo_query

        pipeline.append({"$vectorSearch": vector_search_stage})
        pipeline.append({
            "$addFields": {
                "numeric_price": {
                    "$convert": {
                        "input": "$price",
                        "to": "double",
                        "onError": 0.0,
                        "onNull": 0.0
                    }
                }
            }
        })

    try:
        return list(products_collection.aggregate(pipeline))
    except Exception as e:
        print(f"Aggregation failed: {e}. Falling back to standard find.")
        if search_keyword == "all":
            return list(products_collection.find({}).limit(15))
        return list(products_collection.find(match_stage).limit(15))


def format_product_context(products):
    """Format MongoDB document details and fetch actual reviews from the database."""
    if not products:
        return "No matching products found in our catalog."
    
    blocks = []
    for p in products:
        p_id = p.get("_id")
        
        reviews_list = []
        if p_id:
            try:
                cursor = db["reviews"].find({"product": p_id}).limit(5)
                for r in cursor:
                    rating = r.get("rating", "N/A")
                    comment = r.get("comment", "")
                    pros = r.get("pros", "")
                    cons = r.get("cons", "")
                    reviews_list.append(f"- [{rating}/5 Stars] Comment: {comment} (Pros: {pros} | Cons: {cons})")
            except Exception as e:
                print(f"Error fetching reviews: {e}")
        
        reviews_text = "\n  ".join(reviews_list) if reviews_list else "No customer reviews available yet for this product."
        
        blocks.append(
            f"Product: {p.get('name', 'N/A')}\n"
            f"- Category: {p.get('category', 'N/A')}\n"
            f"- Origin: {p.get('origin', 'N/A')}\n"
            f"- Price: {p.get('price', 'N/A')} TND\n"
            f"- Sowing Period: {p.get('sowingPeriod', 'N/A')}\n"
            f"- Culture Tips: {p.get('cultureTips', 'N/A')}\n"
            f"- Description: {p.get('description', '')}\n"
            f"- Actual Customer Reviews:\n  {reviews_text}\n"
            f"-------------------------"
        )
    return "\n".join(blocks)


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        user_msg = request.message
        chat_history = request.history
        
        # 1. Detect comparative intent
        force_all = should_force_all_products(user_msg)
        
        # 2. Run our global, scalable JSON NLU Parser!
        nlu_data = extract_search_intent(user_msg, chat_history)
        search_keyword = nlu_data.get("keyword", "none")
        origin_country = nlu_data.get("origin", "none")
        
        if force_all:
            search_keyword = "all"
            
        print(f"Original Msg: '{user_msg}' -> NLU Extracted: Keyword='{search_keyword}', Origin='{origin_country}'")
        
        # 3. Fetch relevant database context
        matching_products = search_local_products_vector(search_keyword, origin_country, user_msg, force_all)
        context = format_product_context(matching_products)
        
        # 4. Greeting Interceptor: If it's a simple hello, override context to prevent empty results confusion
        if is_simple_greeting(user_msg):
            context = "The user is just greeting you. Introduce yourself warmly as Fechka, the Mago Seeds botanical assistant, and ask what they want to plant today. Do not say that no products were found."

        # 5. System Instructions
        system_prompt = (
            "You are 'Fechka', an expert botanical assistant for our seed store.\n\n"
            "CRITICAL PRODUCT INVENTORY RULES (STRICTLY ENFORCED):\n"
            "1. When discussing products, seeds, catalog listings, or varieties available in our store, you MUST ONLY list the products provided in the 'Database Context' below. "
            "It is STRICTLY FORBIDDEN to invent, hallucinate, or list any product names, varieties, or prices that are not explicitly present in the provided Database Context.\n"
            "2. If the database context has only 2 products (such as only Bar Laabid and Baklouti), you must ONLY list those 2 products. Do NOT use your general knowledge or imagination to list a 3rd, 4th, or 5th product. If there are only 2, state clearly that those are the only ones we carry.\n"
            "3. If the database context says 'No matching products found in our catalog', but you were *just* discussing a specific product "
            "in your recent conversation history, you may use details from your previous messages to answer follow-up questions. Otherwise, politely state that we don't have matches and suggest other general categories.\n"
            "4. Our prices are in TND (Tunisian Dinar). Always display prices in TND or DT (Dinar Tunisien) exactly as they are written in the Database Context. Do NOT invent prices for non-existent products.\n"
            "5. If the Database Context only contains one category of products (e.g., only peppers) due to a filtered query, do NOT tell the user that we only sell that category. "
            "Simply explain that those are the matches for their specific search, and mention that we also carry other categories like tomatoes, cucumbers, or aubergines (without making up specific product names for them).\n"
            "6. When asked about customer reviews, ratings, or what buyers think of a product, you MUST strictly summarize the actual reviews provided in the 'Database Context'. "
            "If the context says 'No customer reviews available yet', you MUST politely state that we don't have any reviews for this product yet. "
            "NEVER hallucinate, invent, or write fictional customer reviews.\n"
            "7. GEOGRAPHIC & ATTRIBUTE FILTERING: Pay close attention to descriptors in the user's question (e.g., 'Tunisian', 'sweet', 'hot', 'heirloom', 'french', 'danish'). "
            "You MUST only list products from the Database Context that actually match these criteria. Only group products under geographical labels (like 'French seeds' or 'Danish seeds') if their origin explicitly matches that country.\n"
            "8. LIST COMPLETENESS: You must NEVER omit, skip, or summarize matching products from the Database Context. "
            "If 5 products match in the context, you must list all 5. But do NOT add products outside the context.\n"
            "9. GENERAL BOTANICAL ADVICE LIMITATION: You may use your general botanical knowledge ONLY for advice on gardening, care, watering, soil, sowing depths, or climate. "
            "You are STRICTLY FORBIDDEN from using general knowledge to name, invent, or describe any plant varieties, seed packets, or products that we do not have in our Database Context.\n\n"
            f"Database Context:\n{context}"
        )
        
        # 6. Construct message payloads preserving conversation history
        groq_messages = []
        groq_messages.append({"role": "system", "content": system_prompt})
        
        # Append recent history
        for msg in chat_history[-5:-1]:
            role = "assistant" if msg.get("isBot") else "user"
            groq_messages.append({"role": role, "content": msg.get("text")})
            
        # Append current user message
        groq_messages.append({"role": "user", "content": user_msg})
        
        # 7. Request completion from Groq (with zero temperature for absolute accuracy)
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=groq_messages,
            temperature=0.0,
            max_tokens=1200
        )
        
        return {"response": completion.choices[0].message.content}

    except Exception as e:
        import traceback
        print("\n=== !!! CHATBOT ERROR DETECTED !!! ===")
        traceback.print_exc()
        print("======================================\n")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/embed-product")
async def embed_product_endpoint(request: EmbedRequest):
    """
    On-Demand Product Text Embedding Generator.
    Accepts a Product ID, constructs a flattened text string of all its current schema fields,
    computes the vector with our SentenceTransformer model, and writes it directly to the product.
    """
    try:
        product_id = request.product_id
        if not product_id:
            raise HTTPException(status_code=400, detail="Missing product_id")

        p = products_collection.find_one({"_id": ObjectId(product_id)})
        if not p:
            raise HTTPException(status_code=404, detail="Product not found in database")

        # Flatten nested specifications array of objects
        specs_list = []
        specifications = p.get("specifications", [])
        for spec in specifications:
            label = spec.get("label", "")
            value = spec.get("value", "")
            if label and value:
                specs_list.append(f"{label}: {value}")
        specs_text = ". ".join(specs_list)

        # Map descriptive schema fields
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
        
        if specs_text:
            text_parts.append(f"Specifications: {specs_text}")
            
        # Combine everything into a single clean text string
        text_to_embed = ". ".join([part for part in text_parts if part.strip()])
        
        # Generate the vector embedding
        vector = embedding_model.encode(text_to_embed).tolist()
        
        # Save vector back to MongoDB product record
        products_collection.update_one(
            {"_id": ObjectId(product_id)},
            {"$set": {"embedding": vector}}
        )
        return {"status": "success", "message": f"Successfully updated embedding for product: {p.get('name')}"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/related-products")
async def related_products_endpoint(request: RelatedRequest):
    """
    Semantic Related Products Recommender.
    Utilizes MongoDB Atlas Vector Search on the 'embedding' field of products
    to find the top 3 most semantically similar seeds, excluding the current product itself.
    """
    try:
        p_id = request.product_id
        if not p_id:
            raise HTTPException(status_code=400, detail="Missing product_id")

        current_product = products_collection.find_one({"_id": ObjectId(p_id)})
        if not current_product:
            raise HTTPException(status_code=404, detail="Product not found")

        embedding = current_product.get("embedding")
        
        # Fallback A: If product does not have an embedding, pull items in the same category
        if not embedding:
            category = current_product.get("category", "")
            related = list(products_collection.find({
                "category": category,
                "_id": {"$ne": ObjectId(p_id)}
            }).limit(3))
        else:
            # Atlas Vector Search query
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index",
                        "path": "embedding",
                        "queryVector": embedding,
                        "numCandidates": 50,
                        "limit": 4
                    }
                },
                {
                    "$match": {
                        "_id": {"$ne": ObjectId(p_id)}
                    }
                },
                {
                    "$limit": 3
                }
            ]
            related = list(products_collection.aggregate(pipeline))

            # Fallback B: If Atlas Vector Search returned nothing (e.g. index build pending), pull same category
            if not related:
                category = current_product.get("category", "")
                related = list(products_collection.find({
                    "category": category,
                    "_id": {"$ne": ObjectId(p_id)}
                }).limit(3))

        # Convert all ObjectIds recursively to strings (and remove embed vectors) to prevent jsonable_encoder crashes
        clean_related = serialize_mongo_data(related)
        for item in clean_related:
            if "embedding" in item:
                del item["embedding"]

        return clean_related

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))