from typing import Optional

import httpx
from config import API_BASE_URL, API_KEY


async def send_event(event_name: str, payload: Optional[dict] = None, bot_user_id: Optional[int] = None, lead_id=None):
    if not API_KEY:
        return
    data = {
        "event_name": event_name,
        "payload": payload or {},
    }
    if bot_user_id:
        data["bot_user_id"] = bot_user_id
    if lead_id:
        data["lead_id"] = str(lead_id)  # UUID нужно передавать как строку
    headers = {"Authorization": f"Api-Key {API_KEY}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            await client.post(f"{API_BASE_URL.rstrip('/')}/analytics/events", json=data, headers=headers)
        except Exception:
            # Ошибки аналитики не должны ломать пользовательский поток
            return

