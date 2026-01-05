import asyncio
import logging
from typing import Optional

import httpx

from config import API_BASE_URL, API_KEY

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Базовый класс для ошибок API"""
    pass


class ApiClientError(ApiError):
    """Ошибка клиента (4xx)"""
    pass


class ApiServerError(ApiError):
    """Ошибка сервера (5xx)"""
    pass


class ApiTimeoutError(ApiError):
    """Таймаут запроса"""
    pass


class ApiNetworkError(ApiError):
    """Сетевая ошибка"""
    pass


class ApiClient:
    def __init__(self, base_url: str = API_BASE_URL, api_key: str = API_KEY, max_retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(timeout=10.0)

    def _headers(self):
        return {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _request_with_retry(self, method: str, url: str, **kwargs):
        """Выполнить запрос с retry механизмом"""
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = await self.client.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp
            except httpx.TimeoutException as e:
                last_error = ApiTimeoutError(f"Таймаут запроса: {e}")
                logger.warning(f"API timeout (attempt {attempt}/{self.max_retries}): {url}")
            except httpx.ConnectError as e:
                last_error = ApiNetworkError(f"Ошибка подключения: {e}")
                logger.warning(f"API connection error (attempt {attempt}/{self.max_retries}): {url}")
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                if status_code >= 500:
                    last_error = ApiServerError(f"Ошибка сервера ({status_code}): {e.response.text}")
                    logger.warning(f"API server error {status_code} (attempt {attempt}/{self.max_retries}): {url}")
                elif status_code >= 400:
                    # 4xx ошибки не ретраим
                    raise ApiClientError(f"Ошибка клиента ({status_code}): {e.response.text}")
                else:
                    raise
            except httpx.RequestError as e:
                last_error = ApiNetworkError(f"Сетевая ошибка: {e}")
                logger.warning(f"API network error (attempt {attempt}/{self.max_retries}): {url}")

            # Экспоненциальная задержка: 1s, 2s, 4s
            if attempt < self.max_retries:
                delay = 2 ** (attempt - 1)
                logger.info(f"Retrying in {delay}s...")
                await asyncio.sleep(delay)

        # Все попытки исчерпаны
        raise last_error

    async def get_settings(self):
        resp = await self._request_with_retry("GET", f"{self.base_url}/settings", headers=self._headers())
        return resp.json()

    async def get_cities(self):
        resp = await self._request_with_retry("GET", f"{self.base_url}/dicts/cities", headers=self._headers())
        return resp.json()

    async def get_categories(self):
        resp = await self._request_with_retry("GET", f"{self.base_url}/dicts/categories", headers=self._headers())
        return resp.json()

    async def get_training_formats(self):
        resp = await self._request_with_retry("GET", f"{self.base_url}/dicts/training-formats", headers=self._headers())
        return resp.json()

    async def get_training_time_slots(self):
        resp = await self._request_with_retry("GET", f"{self.base_url}/dicts/training-time-slots", headers=self._headers())
        return resp.json()

    async def get_schools(self, city_id: int):
        resp = await self._request_with_retry(
            "GET", f"{self.base_url}/schools", params={"city_id": city_id}, headers=self._headers()
        )
        return resp.json()

    async def get_school_detail(self, school_id: int, category_id: Optional[int] = None, training_format_id: Optional[int] = None, training_time_id: Optional[int] = None):
        params = {}
        if category_id:
            params["category_id"] = category_id
        if training_format_id:
            params["training_format_id"] = training_format_id
        if training_time_id:
            params["training_time_id"] = training_time_id
        resp = await self._request_with_retry("GET", f"{self.base_url}/schools/{school_id}", params=params, headers=self._headers())
        return resp.json()

    async def get_instructors(self, city_id: int, category_id: int, gearbox: Optional[str] = None, gender: Optional[str] = None):
        params = {"city_id": city_id, "category_id": category_id}
        if gearbox:
            params["gearbox"] = gearbox
        if gender:
            params["gender"] = gender
        resp = await self._request_with_retry("GET", f"{self.base_url}/instructors", params=params, headers=self._headers())
        return resp.json()

    async def get_instructor_detail(self, instructor_id: int):
        resp = await self._request_with_retry("GET", f"{self.base_url}/instructors/{instructor_id}", headers=self._headers())
        return resp.json()

    async def get_online_tariff(self, tariff_plan_code: str, category_id: Optional[int] = None, school_id: Optional[int] = None):
        """
        Получить тариф онлайн-продукта по коду тарифного плана.
        Если school_id указан, ищем тариф у конкретной школы.
        Если category_id указан, фильтруем по категории.
        """
        # Если school_id указан, используем school_detail
        if school_id:
            detail = await self.get_school_detail(school_id, category_id=category_id, training_format_id=1)  # 1 = Онлайн
            tariffs = detail.get("tariffs", [])
            for tariff in tariffs:
                tariff_plan = tariff.get("tariff_plan", {})
                if isinstance(tariff_plan, dict) and tariff_plan.get("code") == tariff_plan_code:
                    # Убеждаемся, что school_id есть в тарифе
                    if "school_id" not in tariff:
                        tariff["school_id"] = school_id
                    return tariff
            return None
        
        # Если school_id не указан, ищем через список школ
        # Получаем все города и ищем тарифы
        cities = await self.get_cities()
        for city in cities:
            schools = await self.get_schools(city["id"])
            for school in schools:
                current_school_id = school["id"]
                detail = await self.get_school_detail(current_school_id, category_id=category_id, training_format_id=1)
                tariffs = detail.get("tariffs", [])
                for tariff in tariffs:
                    tariff_plan = tariff.get("tariff_plan", {})
                    if isinstance(tariff_plan, dict) and tariff_plan.get("code") == tariff_plan_code:
                        # Убеждаемся, что school_id есть в тарифе
                        if "school_id" not in tariff:
                            tariff["school_id"] = current_school_id
                        return tariff
        return None

    async def create_lead(self, payload: dict):
        resp = await self._request_with_retry("POST", f"{self.base_url}/leads", json=payload, headers=self._headers())
        return resp.json()

    async def close(self):
        await self.client.aclose()

