import os
from typing import List, Dict
from pymongo import MongoClient
from dotenv import load_dotenv
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModel
from bson import ObjectId
import torch

load_dotenv()

class AdvancedRecommendationEngine:
    """
    Multi-Method Recommendation Engine combining:
    1. TF-IDF for traditional text-based similarity (25% weight)
    2. BERT Transformers for semantic understanding (35% weight)
    3. SentenceTransformer for optimized similarity (40% weight)
    4. Hybrid approach for best results
    """
    
    def __init__(self):
        print("[RECOMMENDATION_ENGINE] Initializing...")
        
        self.mongo_uri = os.getenv("MONGO_URI")
        if not self.mongo_uri:
            raise ValueError("MONGO_URI is missing!")
        
        try:
            self.mongo_client = MongoClient(self.mongo_uri)
            self.db = self.mongo_client.get_default_database()
            self.products_collection = self.db["products"]
            print("[✓] MongoDB connected")
        except Exception as e:
            print(f"[✗] MongoDB connection failed: {e}")
            raise
        
        # Initialize Models
        print("[RECOMMENDATION_ENGINE] Loading BERT...")
        self.bert_model_name = "bert-base-uncased"
        self.bert_tokenizer = AutoTokenizer.from_pretrained(self.bert_model_name)
        self.bert_model = AutoModel.from_pretrained(self.bert_model_name)
        
        print("[RECOMMENDATION_ENGINE] Loading SentenceTransformer...")
        self.sentence_transformer = SentenceTransformer("all-MiniLM-L6-v2")
        
        print("[RECOMMENDATION_ENGINE] Initializing TF-IDF...")
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=100,
            stop_words='english',
            lowercase=True,
            ngram_range=(1, 2)
        )
        
        self.products_cache = []
        self.tfidf_matrix = None
        self.bert_embeddings = []
    
    def preprocess_text(self, text: str) -> str:
        """Text preprocessing"""
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def flatten_product_text(self, product: Dict) -> str:
        """Convert product to searchable text"""
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
            specs_text
        ]
        
        full_text = " ".join([p for p in text_parts if p and isinstance(p, str)])
        return self.preprocess_text(full_text)
    
    def build_tfidf_matrix(self):
        """METHOD 1: TF-IDF Vectorization"""
        print("\n[TF-IDF] Building matrix...")
        texts = [self.flatten_product_text(p) for p in self.products_cache]
        self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(texts)
        print(f"[✓] TF-IDF shape: {self.tfidf_matrix.shape}")
    
    def compute_bert_embeddings(self):
        """METHOD 2: BERT Transformer Embeddings"""
        print("\n[BERT] Computing embeddings...")
        self.bert_embeddings = []
        
        for product in self.products_cache:
            text = self.flatten_product_text(product)
            
            inputs = self.bert_tokenizer(
                text,
                return_tensors="pt",
                max_length=512,
                truncation=True,
                padding=True
            )
            
            with torch.no_grad():
                outputs = self.bert_model(**inputs)
            
            cls_embedding = outputs.last_hidden_state[:, 0, :].numpy().flatten()
            self.bert_embeddings.append(cls_embedding)
        
        self.bert_embeddings = np.array(self.bert_embeddings)
        print(f"[✓] BERT embeddings shape: {self.bert_embeddings.shape}")
    
    def compute_sentence_transformer_embeddings(self):
        """METHOD 3: SentenceTransformer Embeddings"""
        print("\n[SentenceTransformer] Computing embeddings...")
        texts = [self.flatten_product_text(p) for p in self.products_cache]
        embeddings = self.sentence_transformer.encode(texts, convert_to_numpy=True)
        print(f"[✓] SentenceTransformer shape: {embeddings.shape}")
        return embeddings
    
    def tfidf_similarity(self, query_idx: int, top_k: int = 3) -> List[Dict]:
        """Find similar products using TF-IDF"""
        query_vector = self.tfidf_matrix[query_idx]
        similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
        similar_indices = np.argsort(similarities)[::-1][1:top_k+1]
        
        results = []
        for idx in similar_indices:
            results.append({
                "product": self.products_cache[idx],
                "similarity_score": float(similarities[idx]),
                "method": "TF-IDF"
            })
        return results
    
    def bert_similarity(self, query_idx: int, top_k: int = 3) -> List[Dict]:
        """Find similar products using BERT"""
        query_vector = self.bert_embeddings[query_idx].reshape(1, -1)
        similarities = cosine_similarity(query_vector, self.bert_embeddings).flatten()
        similar_indices = np.argsort(similarities)[::-1][1:top_k+1]
        
        results = []
        for idx in similar_indices:
            results.append({
                "product": self.products_cache[idx],
                "similarity_score": float(similarities[idx]),
                "method": "BERT"
            })
        return results
    
    def sentence_transformer_similarity(self, query_idx: int, top_k: int = 3) -> List[Dict]:
        """Find similar products using SentenceTransformer"""
        embeddings = self.compute_sentence_transformer_embeddings()
        query_vector = embeddings[query_idx].reshape(1, -1)
        similarities = cosine_similarity(query_vector, embeddings).flatten()
        similar_indices = np.argsort(similarities)[::-1][1:top_k+1]
        
        results = []
        for idx in similar_indices:
            results.append({
                "product": self.products_cache[idx],
                "similarity_score": float(similarities[idx]),
                "method": "SentenceTransformer"
            })
        return results
    
    def hybrid_recommendation(self, query_idx: int, top_k: int = 3) -> List[Dict]:
        """METHOD 4: Hybrid approach (25% TF-IDF, 35% BERT, 40% SentenceTransformer)"""
        # Get embeddings
        embeddings = self.compute_sentence_transformer_embeddings()
        
        # TF-IDF scores
        tfidf_query = self.tfidf_matrix[query_idx]
        tfidf_scores = cosine_similarity(tfidf_query, self.tfidf_matrix).flatten()
        
        # BERT scores
        bert_query = self.bert_embeddings[query_idx].reshape(1, -1)
        bert_scores = cosine_similarity(bert_query, self.bert_embeddings).flatten()
        
        # SentenceTransformer scores
        st_query = embeddings[query_idx].reshape(1, -1)
        st_scores = cosine_similarity(st_query, embeddings).flatten()
        
        # Normalize and combine
        hybrid_scores = {}
        for i in range(len(self.products_cache)):
            if i == query_idx:
                continue
            hybrid_scores[i] = (0.25 * tfidf_scores[i] + 0.35 * bert_scores[i] + 0.40 * st_scores[i])
        
        sorted_indices = sorted(hybrid_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        results = []
        for idx, score in sorted_indices:
            results.append({
                "product": self.products_cache[idx],
                "similarity_score": float(score),
                "method": "Hybrid",
                "tfidf_component": float(tfidf_scores[idx]),
                "bert_component": float(bert_scores[idx]),
                "semantic_component": float(st_scores[idx])
            })
        return results
    
    def load_products(self):
        """Load all products from MongoDB"""
        print("\n[CACHE] Loading products...")
        self.products_cache = list(self.products_collection.find({}))
        print(f"[✓] Loaded {len(self.products_cache)} products")
    
    def initialize_all_embeddings(self):
        """Initialize all embedding types"""
        self.load_products()
        self.build_tfidf_matrix()
        self.compute_bert_embeddings()
        print("\n[✓] Recommendation Engine ready!")
    
    def get_recommendations(self, product_id: str, method: str = "hybrid", top_k: int = 3) -> List[Dict]:
        """Get recommendations using specified method"""
        query_idx = None
        for i, p in enumerate(self.products_cache):
            if str(p['_id']) == product_id:
                query_idx = i
                break
        
        if query_idx is None:
            raise ValueError(f"Product {product_id} not found")
        
        if method == "tfidf":
            return self.tfidf_similarity(query_idx, top_k)
        elif method == "bert":
            return self.bert_similarity(query_idx, top_k)
        elif method == "sentence_transformer":
            return self.sentence_transformer_similarity(query_idx, top_k)
        elif method == "hybrid":
            return self.hybrid_recommendation(query_idx, top_k)
        else:
            raise ValueError(f"Unknown method: {method}")
    
    def embed_single_product(self, product_id: str) -> str:
        """Embed a single product"""
        try:
            p = self.products_collection.find_one({"_id": ObjectId(product_id)})
            if not p:
                return f"Product {product_id} not found"
            
            text = self.flatten_product_text(p)
            vector = self.sentence_transformer.encode([text], convert_to_numpy=True)[0].tolist()
            
            self.products_collection.update_one(
                {"_id": ObjectId(product_id)},
                {"$set": {"embedding": vector}}
            )
            return f"Successfully embedded: {p.get('name')}"
        except Exception as e:
            return f"Error embedding product: {str(e)}"
