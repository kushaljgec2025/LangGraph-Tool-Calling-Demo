def run(amount: float, discount_percent: float) -> dict:
    discounted_amount = float(amount) * (1.0 - (float(discount_percent) / 100.0))
    return {"result": round(discounted_amount, 2), "status": "success"}