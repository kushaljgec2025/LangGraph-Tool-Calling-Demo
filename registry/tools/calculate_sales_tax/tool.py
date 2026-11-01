def run(amount: float, tax_percent: float) -> dict:
    total_with_tax = float(amount) * (1.0 + (float(tax_percent) / 100.0))
    return {"result": round(total_with_tax, 2), "status": "success"}