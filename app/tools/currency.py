from __future__ import annotations
import asyncio
import httpx
from app.config import get_settings

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"


async def convert(amount: float, base: str, target: str) -> float:
    base, target = base.upper(), target.upper()
    if amount == 0 or base == target:
        return round(amount, 2)

    settings = get_settings()
    params = {"amount": amount, "from": base, "to": target}
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            resp = await client.get(f"{FRANKFURTER_URL}?{httpx.QueryParams(params)}")
            print(resp)
            resp.raise_for_status()
            rates = resp.json().get("rates", {})
        if target in rates:
            return round(float(rates[target]), 2)
    except (httpx.HTTPError, ValueError, KeyError):
        print(f"Currency conversion failed for {amount} {base} -> {target}")
        pass
    return round(amount, 2)


if __name__ == "__main__":
    print("100 EUR ->", asyncio.run(convert(100, "EUR", "USD")), "USD")
