import os
import re
import json
from typing import List, Dict, Tuple
from pymongo import MongoClient
from dotenv import load_dotenv
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from transformers import pipeline
import torch

load_dotenv()

class AdvancedNLPEngine:
    """
    Multi-Method NLP Engine demonstrating:
    1. Intent Classification (BERT Zero-Shot)
    2. Entity Recognition (Regex + Named Entity Recognition)
    3. TF-IDF for keyword-based search
    4. Semantic Search (SentenceTransformer)
    5. Hybrid Search (Combined approach)
    """
    
    def __init__(self):
        print("[NLP_ENGINE] Initializing Advanced NLP Engine...")
        
        # MongoDB Connection
        self.mongo_uri = os.getenv("MONGO_URI")
        if not self.mongo_uri:
            raise ValueError("MONGO_URI is missing from .env!")
        
        try:
            self.mongo_client = MongoClient(self.mongo_uri)
            self.db = self.mongo_client.get_default_database()
            self.products_collection = self.db["products"]
            self.reviews_collection = self.db["reviews"]
            print("[✓] MongoDB connected successfully")
        except Exception as e:
            print(f"[✗] MongoDB connection failed: {e}")
            raise
        
        # NLP Models
        print("[NLP_ENGINE] Loading BERT Intent Classifier...")
        self.intent_classifier = pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
            device=0 if torch.cuda.is_available() else -1
        )
        
        print("[NLP_ENGINE] Loading SentenceTransformer...")
        self.sentence_transformer = SentenceTransformer("all-MiniLM-L6-v2")
        
        print("[NLP_ENGINE] Initializing TF-IDF Vectorizer...")
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=500,
            stop_words='english',
            lowercase=True,
            ngram_range=(1, 3),
            min_df=1
        )
        
        # Define intents for classification
        self.intents = [
            "product_search",
            "price_inquiry",
            "product_comparison",
            "geographic_filter",
            "customer_reviews",
            "planting_advice",
            "general_greeting",
            "product_recommendation"
        ]
        
        # Entity patterns for extraction
        self.entity_patterns = {
            "PRODUCT": r"\b(tomato|pepper|cucumber|eggplant|carrot|lettuce|bean|squash|zucchini|brad|baklouti|bar laabid|beet|onion|garlic|spinach)\b",
            "LOCATION": r"\b(france|italy|tunisia|denmark|spain|usa|germany|switzerland|netherlands|belgium|morocco|egypt|algeria|jordan)\b",
            "PRICE": r"\b(\d+\.?\d*)\s*(tnd|dt|dinar|dinars)\b",
            "ADJECTIVE": r"\b(sweet|hot|spicy|organic|heirloom|hybrid|early|late|mini|giant|premium|affordable)\b",
            "COMPARATIVE": r"\b(cheapest|priciest|most expensive|least expensive|best|worst|top|expensive|cheap)\b"
        }
        
        # Cache for products
        self.products_cache = []
        self.product_embeddings = None
        self.product_tfidf_matrix = None
        
    def preprocess_text(self, text: str) -> str:
        """
        NLP Preprocessing Pipeline:
        - Lowercase conversion
        - Remove special characters & punctuation
        - Normalize whitespace
        """
        text = text.lower().strip()
        text = re.sub(r'[^\w\s?!.]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def tokenize(self, text: str) -> List[str]:
        """Basic tokenization"""
        return text.split()
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        METHOD 1: Entity Recognition using regex patterns
        Demonstrates NER concept
        """
        entities = {}
        text_lower = text.lower()
        
        for entity_type, pattern in self.entity_patterns.items():
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            if matches:
                entities[entity_type] = list(set(matches))
        
        return entities
    
    def classify_intent(self, user_message: str) -> Tuple[str, float]:
        """
        METHOD 2: Intent Classification using BERT Zero-Shot Classification
        Determines what the user wants to do
        """
        print(f"\n[INTENT_CLASSIFIER] Analyzing: '{user_message}'")
        
        try:
            result = self.intent_classifier(
                user_message,
                self.intents,
                multi_class=False
            )
            
            intent = result['labels'][0]
            confidence = result['scores'][0]
            
            print(f"[✓] Intent: {intent} (Confidence: {confidence:.2%})")
            return intent, confidence
        
        except Exception as e:
            print(f"[✗] Intent classification failed: {e}")
            return "general_greeting", 0.0
    
    def load_products(self):
        """Load all products from MongoDB"""
        print("\n[CACHE] Loading products from MongoDB...")
        try:
            self.products_cache = list(self.products_collection.find({}))
            print(f"[✓] Loaded {len(self.products_cache)} products")
        except Exception as e:
            print(f"[✗] Failed to load products: {e}")
            self.products_cache = []
    
    def flatten_product_text(self, product: Dict) -> str:
        """Convert product document into searchable text"""
        specs_list = []
        specifications = product.get("specifications", [])
        
        for spec in specifications:
            if isinstance(spec, dict):
                label = spec.get("label", "")
                value = spec.get("value", "")
                if label and value:
                    specs_list.append(f"{label} {value}")
        
        specs_text = " ".join(specs_list)
        
        text_parts = [
            product.get('name', ''),
            product.get('category', ''),
            product.get('origin', ''),
            product.get('harvestPeriod', ''),
            product.get('sowingPeriod', ''),
            product.get('cultureTips', ''),
            product.get('description', ''),
            product.get('shortDescription', ''),
            product.get('content', ''),
            product.get('type', ''),
            specs_text
        ]
        
        full_text = " ".join([p for p in text_parts if p and isinstance(p, str)])
        return self.preprocess_text(full_text)
    
    def build_tfidf_matrix(self):
        """
        METHOD 3: TF-IDF Vectorization
        Convert products to TF-IDF vectors for keyword-based search
        Demonstrates traditional NLP text representation
        """
        print("\n[TF-IDF] Building product TF-IDF matrix...")
        if not self.products_cache:
            print("[✗] No products in cache. Cannot build TF-IDF matrix.")
            return
        
        try:
            texts = [self.flatten_product_text(p) for p in self.products_cache]
            self.product_tfidf_matrix = self.tfidf_vectorizer.fit_transform(texts)
            print(f"[✓] TF-IDF Matrix shape: {self.product_tfidf_matrix.shape}")
        except Exception as e:
            print(f"[✗] TF-IDF build failed: {e}")
    
    def build_semantic_embeddings(self):
        """
        METHOD 4: Semantic Embeddings using SentenceTransformer
        Captures semantic meaning for better search
        Demonstrates transformer-based embeddings
        """
        print("\n[EMBEDDINGS] Computing semantic embeddings...")
        if not self.products_cache:
            print("[✗] No products in cache. Cannot build embeddings.")
            return
        
        try:
            texts = [self.flatten_product_text(p) for p in self.products_cache]
            self.product_embeddings = self.sentence_transformer.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=True
            )
            print(f"[✓] Embeddings shape: {self.product_embeddings.shape}")
        except Exception as e:
            print(f"[✗] Embedding computation failed: {e}")
    
    def tfidf_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search using TF-IDF similarity
        Good for: Exact keyword matching
        """
        print(f"\n[TF-IDF_SEARCH] Query: '{query}'")
        
        if self.product_tfidf_matrix is None:
            print("[✗] TF-IDF matrix not initialized")
            return []
        
        try:
            query_vector = self.tfidf_vectorizer.transform([query])
            similarities = cosine_similarity(query_vector, self.product_tfidf_matrix).flatten()
            
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                if similarities[idx] > 0:
                    results.append({
                        "product": self.products_cache[idx],
                        "score": float(similarities[idx]),
                        "method": "TF-IDF"
                    })
            
            print(f"[✓] Found {len(results)} results via TF-IDF")
            return results
        except Exception as e:
            print(f"[✗] TF-IDF search failed: {e}")
            return []
    
    def semantic_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search using Semantic Embeddings
        Good for: Understanding meaning beyond keywords
        """
        print(f"\n[SEMANTIC_SEARCH] Query: '{query}'")
        
        if self.product_embeddings is None:
            print("[✗] Semantic embeddings not initialized")
            return []
        
        try:
            query_embedding = self.sentence_transformer.encode([query], convert_to_numpy=True)
            similarities = cosine_similarity(query_embedding, self.product_embeddings).flatten()
            
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                results.append({
                    "product": self.products_cache[idx],
                    "score": float(similarities[idx]),
                    "method": "SemanticSearch"
                })
            
            print(f"[✓] Found {len(results)} results via semantic search")
            return results
        except Exception as e:
            print(f"[✗] Semantic search failed: {e}")
            return []
    
    def hybrid_search(self, query: str, top_k: int = 5, alpha: float = 0.5) -> List[Dict]:
        """
        METHOD 5: Hybrid Search combining TF-IDF + Semantic
        alpha: weight for semantic (0.5 = 50% semantic, 50% TF-IDF)
        
        Demonstrates combining multiple NLP techniques for better results
        """
        print(f"\n[HYBRID_SEARCH] Query: '{query}' (α={alpha})")
        
        if self.product_tfidf_matrix is None or self.product_embeddings is None:
            print("[✗] TF-IDF or embeddings not initialized. Falling back to semantic search.")
            return self.semantic_search(query, top_k)
        
        try:
            # Get TF-IDF scores
            query_tfidf = self.tfidf_vectorizer.transform([query])
            tfidf_scores = cosine_similarity(query_tfidf, self.product_tfidf_matrix).flatten()
            
            # Normalize to 0-1
            tfidf_min, tfidf_max = tfidf_scores.min(), tfidf_scores.max()
            tfidf_scores = (tfidf_scores - tfidf_min) / (tfidf_max - tfidf_min + 1e-10)
            
            # Get semantic scores
            query_embedding = self.sentence_transformer.encode([query], convert_to_numpy=True)
            semantic_scores = cosine_similarity(query_embedding, self.product_embeddings).flatten()
            
            # Combine: hybrid_score = α * semantic + (1-α) * tfidf
            hybrid_scores = (alpha * semantic_scores) + ((1 - alpha) * tfidf_scores)
            
            top_indices = np.argsort(hybrid_scores)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                results.append({
                    "product": self.products_cache[idx],
                    "score": float(hybrid_scores[idx]),
                    "method": "Hybrid",
                    "tfidf_component": float(tfidf_scores[idx]),
                    "semantic_component": float(semantic_scores[idx])
                })
            
            print(f"[✓] Found {len(results)} results via hybrid search")
            return results
        except Exception as e:
            print(f"[✗] Hybrid search failed: {e}")
            return self.semantic_search(query, top_k)
    
    def filter_by_entity(self, products: List[Dict], entities: Dict) -> List[Dict]:
        """
        Filter products based on extracted entities
        Demonstrates how NER enhances search
        """
        filtered = products
        
        if "LOCATION" in entities:
            location = entities["LOCATION"][0]
            filtered = [
                p for p in filtered 
                if location.lower() in p.get("origin", "").lower()
            ]
            print(f"[FILTER] Applied location filter: {location}")
        
        if "ADJECTIVE" in entities:
            adjective = entities["ADJECTIVE"][0]
            filtered = [
                p for p in filtered 
                if adjective.lower() in (p.get("description", "") + p.get("type", "")).lower()
            ]
            print(f"[FILTER] Applied adjective filter: {adjective}")
        
        return filtered
    
    def get_product_reviews(self, product_id: str) -> List[Dict]:
        """Fetch product reviews from MongoDB"""
        try:
            reviews = list(self.reviews_collection.find({"product": product_id}).limit(5))
            return reviews
        except Exception as e:
            print(f"[✗] Failed to fetch reviews: {e}")
            return []
    
    def format_product_context(self, products: List[Dict]) -> str:
        """Format products for LLM context with reviews"""
        if not products:
            return "No matching products found in our catalog."
        
        blocks = []
        for p in products:
            try:
                product_id = str(p.get("_id", ""))
                reviews = self.get_product_reviews(product_id)
                
                reviews_text = "\n  ".join([
                    f"★ [{r.get('rating', 'N/A')}/5] {r.get('comment', '')}"
                    for r in reviews
                ]) if reviews else "No reviews yet"
                
                blocks.append(
                    f"🌱 **{p.get('name', 'N/A')}**\n"
                    f"   Category: {p.get('category', 'N/A')}\n"
                    f"   Origin: {p.get('origin', 'N/A')}\n"
                    f"   Price: {p.get('price', 'N/A')} TND\n"
                    f"   Sowing: {p.get('sowingPeriod', 'N/A')}\n"
                    f"   Tips: {p.get('cultureTips', 'N/A')}\n"
                    f"   Reviews:\n  {reviews_text}\n"
                    f"   {'─' * 50}"
                )
            except Exception as e:
                print(f"[✗] Error formatting product: {e}")
                continue
        
        return "\n".join(blocks)
    
    def process_user_query(self, user_message: str, history: List[Dict] = None) -> Dict:
        """
        Complete NLP Pipeline for processing user queries
        Returns structured data for response generation
        """
        if history is None:
            history = []
        
        print("\n" + "="*70)
        print("[PIPELINE] Starting Advanced NLP Query Processing")
        print("="*70)
        
        # STEP 1: Preprocess
        cleaned_message = self.preprocess_text(user_message)
        print(f"[PREPROCESS] Input → {cleaned_message}")
        
        # STEP 2: Extract Entities
        entities = self.extract_entities(cleaned_message)
        print(f"[ENTITIES] Extracted: {entities}")
        
        # STEP 3: Classify Intent
        intent, confidence = self.classify_intent(cleaned_message)
        
        # STEP 4: Choose search strategy based on intent
        if intent == "product_search" or intent == "product_comparison":
            search_results = self.hybrid_search(cleaned_message, top_k=5, alpha=0.5)
            print(f"[SEARCH_STRATEGY] Using hybrid search (product focus)")
        
        elif intent == "price_inquiry" or "COMPARATIVE" in entities:
            search_results = self.tfidf_search(cleaned_message, top_k=5)
            print(f"[SEARCH_STRATEGY] Using TF-IDF search (keyword focus)")
        
        else:
            search_results = self.semantic_search(cleaned_message, top_k=5)
            print(f"[SEARCH_STRATEGY] Using semantic search (meaning focus)")
        
        # STEP 5: Extract products from search results
        products = [r["product"] for r in search_results]
        
        # STEP 6: Apply entity-based filtering
        filtered_products = self.filter_by_entity(products, entities)
        print(f"[FILTER_RESULT] After entity filtering: {len(filtered_products)} products")
        
        # STEP 7: Format context for LLM
        context = self.format_product_context(filtered_products if filtered_products else products)
        
        print("="*70)
        
        return {
            "intent": intent,
            "confidence": confidence,
            "entities": entities,
            "products": filtered_products if filtered_products else products,
            "context": context,
            "search_method": search_results[0].get("method", "Unknown") if search_results else "None",
            "scores": [r.get("score", 0) for r in search_results]
        }
    
    def initialize(self):
        """Initialize all NLP components"""
        print("\n" + "="*70)
        print("[INIT] Starting NLP Engine Initialization")
        print("="*70)
        
        self.load_products()
        self.build_tfidf_matrix()
        self.build_semantic_embeddings()
        
        print("\n[✓] Advanced NLP Engine ready!")
        print("="*70 + "\n")

