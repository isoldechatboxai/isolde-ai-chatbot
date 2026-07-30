import pytest
from app.ai.provider_router import ProviderRouter
from app.ai.context_builder import ContextBuilder
from app.ai.token_cost_tracker import TokenCostTracker

def test_provider_router():
    router = ProviderRouter()
    
    # Test valid routing
    route = router.resolve_provider("3.6 Flash")
    assert route["provider"] == "google"
    assert route["model"] == "gemini-3.6-flash"
    
    # Test fallback routing for unknown model
    fallback = router.resolve_provider("UnknownModel")
    assert fallback["provider"] == "google"
    assert fallback["model"] == "gemini-3.5-flash-lite-extended"

def test_context_builder():
    system_prompt = "You are an expert AI assistant."
    memories = ["User prefers Python code.", "User owns Vilvarai Naturals."]
    rag_chunks = ["Chunk 1: Product inventory details."]
    history = [{"role": "user", "content": "Hello!"}]
    
    payload = ContextBuilder.build_payload(system_prompt, memories, rag_chunks, history)
    
    # Verify payload assembly structure
    assert len(payload) == 4
    assert payload[0]["role"] == "system"
    assert payload[0]["content"] == system_prompt
    assert "User prefers Python code." in payload[1]["content"]
    assert "Chunk 1: Product inventory details." in payload[2]["content"]
    assert payload[3]["role"] == "user"
    assert payload[3]["content"] == "Hello!"

def test_token_cost_tracker():
    # Test financial cost computation
    cost = TokenCostTracker.calculate_cost("gemini-3.5-flash-lite", 1000, 500)
    expected_cost = (1000 / 1000.0) * 0.000075 + (500 / 1000.0) * 0.0003
    assert cost == round(expected_cost, 6)