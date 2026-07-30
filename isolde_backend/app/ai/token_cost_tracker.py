class TokenCostTracker:
    """
    Tracks token consumption and computes financial costs per model per request 
    for enterprise billing and telemetry.
    """
    PRICING_MODEL = {
        "gemini-3.5-flash-lite": {"input": 0.000075, "output": 0.0003}, # per 1k tokens
        "claude-3-7-sonnet": {"input": 0.003, "output": 0.015}
    }

    @classmethod
    def calculate_cost(cls, model_name: str, input_tokens: int, output_tokens: int) -> float:
        rates = cls.PRICING_MODEL.get(model_name, {"input": 0.0001, "output": 0.0004})
        input_cost = (input_tokens / 1000.0) * rates["input"]
        output_cost = (output_tokens / 1000.0) * rates["output"]
        return round(input_cost + output_cost, 6)