import os
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from bson import ObjectId
from dotenv import load_dotenv
from nlp_engine import AdvancedNLPEngine
from recommendation_engine import AdvancedRecommendationEngine

# Load environment variables
load_dotenv()

# ============================================
# FASTAPI APP INITIALIZATION
# ============================================

app = FastAPI(
    title="MAGO SEEDS - Advanced AI Chatbot & Recommendation Service",
    description="Multi-method NLP chatbot with hybrid recommendations",
    version="2.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# INITIALIZE NLP & RECOMMENDATION ENGINES
# ============================================

print("\n" + "="*80)
print("[STARTUP] Initializing MAGO SEEDS AI Service")
print("="*80 + "\n")

nlp_engine = AdvancedNLPEngine()
nlp_engine.initialize()

recommendation_engine = AdvancedRecommendationEngine()
recommendation_engine.initialize_all_embeddings()

# Initialize Groq Client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("[✗] GROQ_API_KEY is missing from .env file!")

groq_client = Groq(api_key=GROQ_API_KEY)
print("[✓] Groq LLM Client initialized")

# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class ChatRequest(BaseModel):
    message: str
    history: list = []

class RecommendationRequest(BaseModel):
    product_id: str
    method: str = "hybrid"  # Options: "tfidf", "bert", "sentence_transformer", "hybrid"
    top_k: int = 3

class EmbedRequest(BaseModel):
    product_id: str

# ============================================
# HELPER FUNCTIONS
# ============================================

def serialize_mongo_data(data):
    """Convert MongoDB ObjectId to string"""
    if isinstance(data, list):
        return [serialize_mongo_data(item) for item in data]
    elif isinstance(data, dict):
        return {k: serialize_mongo_data(v) for k, v in data.items()}
    elif isinstance(data, ObjectId):
        return str(data)
    else:
        return data

def is_simple_greeting(user_query: str) -> bool:
    """Detect if message is just a greeting"""
    q = user_query.lower().strip().strip("?!.🌿")
    greetings = {
        "hello", "hi", "hey", "marhaba", "salam", "bonjour", 
        "salam alaykoum", "aslema", "aslema marhaba", "ahlan", "thanks"
    }
    return q in greetings

# ============================================
# CHAT ENDPOINT
# ============================================

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Advanced NLP Chatbot Endpoint
    
    Uses multi-method NLP pipeline:
    1. Intent Classification (BERT)
    2. Entity Recognition (NER)
    3. Hybrid Search (TF-IDF + Semantic)
    4. Groq LLM for response generation
    """
    try:
        user_msg = request.message
        chat_history = request.history
        
        print(f"\n[CHAT_REQUEST] User: {user_msg}")
        
        # ============================================
        # STEP 1: Run NLP Pipeline
        # ============================================
        nlp_result = nlp_engine.process_user_query(user_msg, chat_history)
        
        intent = nlp_result["intent"]
        entities = nlp_result["entities"]
        context = nlp_result["context"]
        search_method = nlp_result["search_method"]
        
        print(f"[NLP_RESULT] Intent: {intent} | Entities: {list(entities.keys())} | Method: {search_method}")
        
        # ============================================
        # STEP 2: Build System Prompt with Context
        # ============================================
        system_prompt = f"""You are 'Fechka', an expert botanical assistant for MAGO SEEDS store.

CRITICAL RULES (MUST FOLLOW):
1. ONLY recommend products from the provided product context
2. NEVER invent products, prices, or specifications
3. If context shows "No matching products", say so clearly
4. Prices are always in TND (Tunisian Dinar)
5. For customer reviews, use ONLY what's in the context - never fabricate
6. For botanical advice (watering, soil, climate), use your general knowledge
7. Be warm, helpful, and passionate about seeds and gardening!

DETECTED USER INTENT: {intent}
DETECTED ENTITIES: {entities}
SEARCH METHOD USED: {search_method}

PRODUCT CONTEXT:
{context}

Guidelines based on detected intent:
- If product_search: Focus on matching what they're looking for
- If price_inquiry: Highlight relevant pricing
- If product_comparison: Compare products clearly
- If geographic_filter: Emphasize origin information
- If customer_reviews: Share actual reviews
- If planting_advice: Give practical gardening tips
- If general_greeting: Welcome warmly and ask what they need
- If product_recommendation: Suggest based on their needs
"""
        
        # ============================================
        # STEP 3: Handle Simple Greetings
        # ============================================
        if is_simple_greeting(user_msg):
            system_prompt = system_prompt.replace(
                "PRODUCT CONTEXT:",
                "PRODUCT CONTEXT: User is just greeting - introduce yourself and ask what they want to plant.\n\nPRODUCT CONTEXT:"
            )
        
        # ============================================
        # STEP 4: Build Message History for Groq
        # ============================================
        groq_messages = []
        groq_messages.append({"role": "system", "content": system_prompt})
        
        # Add recent chat history
        for msg in chat_history[-5:]:  # Keep last 5 messages
            role = "assistant" if msg.get("isBot") else "user"
            groq_messages.append({"role": role, "content": msg.get("text", "")})
        
        # Add current message
        groq_messages.append({"role": "user", "content": user_msg})
        
        # ============================================
        # STEP 5: Generate Response with Groq
        # ============================================
        print("[GROQ] Generating response...")
        
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=groq_messages,
            temperature=0.7,  # More creative than recommendations
            max_tokens=1500,
            top_p=0.9
        )
        
        response_text = completion.choices[0].message.content
        
        print(f"[GROQ] Response generated ({len(response_text)} chars)")
        
        # ============================================
        # STEP 6: Return Response
        # ============================================
        return {
            "response": response_text,
            "metadata": {
                "intent": intent,
                "entities": entities,
                "search_method": search_method,
                "products_found": len(nlp_result["products"])
            }
        }
    
    except Exception as e:
        import traceback
        print(f"\n[✗] CHAT ERROR: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# RECOMMENDATIONS ENDPOINT
# ============================================

@app.post("/related-products")
async def related_products_endpoint(request: RecommendationRequest):
    """
    Hybrid Product Recommendation Endpoint
    
    Methods:
    - tfidf: Traditional keyword-based (25% weight)
    - bert: Deep semantic understanding (35% weight)
    - sentence_transformer: Optimized similarity (40% weight)
    - hybrid: Combined weighted approach (RECOMMENDED)
    """
    try:
        product_id = request.product_id
        method = request.method
        top_k = request.top_k
        
        print(f"\n[RECOMMENDATION] Product: {product_id} | Method: {method} | Top-K: {top_k}")
        
        # ============================================
        # Get Recommendations
        # ============================================
        recommendations = recommendation_engine.get_recommendations(
            product_id=product_id,
            method=method,
            top_k=top_k
        )
        
        # ============================================
        # Format Response
        # ============================================
        response = []
        for rec in recommendations:
            product = rec['product']
            response.append({
                "_id": str(product.get('_id', '')),
                "name": product.get('name', ''),
                "category": product.get('category', ''),
                "price": product.get('price', ''),
                "origin": product.get('origin', ''),
                "description": product.get('shortDescription', ''),
                "image": product.get('image', ''),
                "similarity_score": rec.get('similarity_score', 0),
                "method_used": rec.get('method', method),
                "tfidf_component": rec.get('tfidf_component'),
                "semantic_component": rec.get('semantic_component')
            })
        
        print(f"[✓] Returned {len(response)} recommendations")
        return response
    
    except Exception as e:
        print(f"[✗] RECOMMENDATION ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# EMBEDDING ENDPOINT
# ============================================

@app.post("/embed-product")
async def embed_product_endpoint(request: EmbedRequest):
    """
    On-Demand Product Embedding Generator
    
    Called when products are created/updated in Express backend
    Generates vector embeddings for semantic search
    """
    try:
        product_id = request.product_id
        
        if not product_id:
            raise HTTPException(status_code=400, detail="Missing product_id")
        
        print(f"\n[EMBED] Generating embedding for product: {product_id}")
        
        # Use recommendation engine to embed
        result = recommendation_engine.embed_single_product(product_id)
        
        print(f"[✓] Embedding completed: {result}")
        return {"status": "success", "message": result}
    
    except Exception as e:
        print(f"[✗] EMBED ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# HEALTH CHECK ENDPOINT
# ============================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "nlp_engine": "ready",
        "recommendation_engine": "ready",
        "groq_llm": "connected"
    }

# ============================================
# COMPARISON ENDPOINT
# ============================================

@app.post("/compare-methods")
async def compare_methods(request: RecommendationRequest):
    """
    Compare all NLP methods for recommendations
    Useful for understanding differences
    """
    try:
        product_id = request.product_id
        top_k = request.top_k
        
        print(f"\n[COMPARE] Product: {product_id}")
        
        results = {}
        
        for method in ["tfidf", "bert", "sentence_transformer", "hybrid"]:
            try:
                recommendations = recommendation_engine.get_recommendations(
                    product_id=product_id,
                    method=method,
                    top_k=top_k
                )
                
                results[method] = []
                for rec in recommendations:
                    product = rec['product']
                    results[method].append({
                        "name": product.get('name', ''),
                        "score": rec.get('similarity_score', 0)
                    })
            except Exception as e:
                results[method] = {"error": str(e)}
        
        print(f"[✓] Comparison completed")
        return results
    
    except Exception as e:
        print(f"[✗] COMPARE ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# STARTUP & SHUTDOWN EVENTS
# ============================================

@app.on_event("startup")
async def startup_event():
    print("\n" + "="*80)
    print("[STARTUP] MAGO SEEDS AI Service is ready!")
    print("="*80)
    print("Endpoints available:")
    print("  POST /chat - Chatbot endpoint")
    print("  POST /related-products - Recommendations")
    print("  POST /embed-product - Generate embeddings")
    print("  POST /compare-methods - Compare NLP methods")
    print("  GET /health - Health check")
    print("="*80 + "\n")

@app.on_event("shutdown")
async def shutdown_event():
    print("\n[SHUTDOWN] MAGO SEEDS AI Service shutting down...\n")

# ============================================
# ROOT ENDPOINT
# ============================================

@app.get("/")
async def root():
    return {
        "name": "MAGO SEEDS AI Service",
        "version": "2.0.0",
        "description": "Advanced NLP Chatbot & Hybrid Recommendation Engine",
        "status": "operational",
        "features": [
            "Intent Classification (BERT Zero-Shot)",
            "Entity Recognition (NER)",
            "TF-IDF Vectorization",
            "BERT Embeddings",
            "SentenceTransformer Embeddings",
            "Hybrid Search",
            "Groq LLM Integration",
            "Dynamic Product Embedding",
            "Semantic Similarity Matching"
        ]
    }

# ============================================
# RUN SERVER
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PYTHON_PORT", 8000))
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
