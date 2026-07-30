# app/workers/embedding_worker.py

import time
import threading
import uuid
from flask import current_app
from app.services.provider_router import embed_text

# 🌟 FIXED: Added underscores to match the function names in rag_service.py
from app.services.rag_service import _chunk_text, _load_index, _save_index

def with_retry(max_retries=3, initial_delay=2, backoff_factor=2):
    """
    Decorator to automatically retry a failed task.
    Implements exponential backoff (e.g., waits 2s, then 4s, then 8s).
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            delay = initial_delay
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        raise e
                    
                    time.sleep(delay)
                    delay *= backoff_factor
        return wrapper
    return decorator

@with_retry(max_retries=3, initial_delay=2)
def _generate_and_save_embeddings(text: str, filename: str, user_id: str):
    """
    Core business logic for processing embeddings.
    Strictly talks to Services and Repositories. NO Route logic here.
    """
    # 1. Chunk the large document text (Using updated _chunk_text)
    chunks = _chunk_text(text)
    if not chunks:
        return
        
    # 2. Load existing vector store database (Using updated _load_index)
    records = _load_index() 
    
    # 3. Generate embeddings for each chunk via the AI Provider
    for chunk in chunks:
        vector = embed_text(chunk)
        
        # Append structured data
        records.append({
            "id": str(uuid.uuid4()),
            "text": chunk,
            "vector": vector,
            "filename": filename,
            "user_id": user_id,
            "timestamp": time.time()
        })
        
    # 4. Save back to the vector store (Using updated _save_index)
    _save_index(records)

def start_embedding_worker(app, text: str, filename: str, user_id: str):
    """
    Kicks off the long-running embedding process in an asynchronous background thread.
    Takes the 'app' instance to ensure the Flask app context is maintained.
    """
    def background_task():
        # Flask requires the app context to access logs, configs, and DB connections inside a thread
        with app.app_context():
            app.logger.info(f"[WORKER START] Generating embeddings for file: {filename}")
            try:
                # Call the core logic which has the @with_retry decorator
                _generate_and_save_embeddings(text, filename, user_id)
                app.logger.info(f"[WORKER SUCCESS] Embeddings generated & saved for: {filename}")
                
            except Exception as e:
                app.logger.error(f"[WORKER FAILED] Embedding task failed for {filename} after retries. Error: {str(e)}")

    # Initialize and start a daemon thread so it doesn't block server shutdown
    thread = threading.Thread(target=background_task)
    thread.daemon = True
    thread.start()