import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


BASE_URL = "https://financialmodelingprep.com/stable"


class FmpClient:
    def __init__(self, api_key, retries=3, retry_delay=2):
        self.api_key = api_key
        self.retries = retries
        self.retry_delay = retry_delay

    def get(self, endpoint, params=None):
        query = {"apikey": self.api_key}
        if params:
            query.update(params)

        url = f"{BASE_URL}/{endpoint}?{urlencode(query)}"

        for attempt in range(1, self.retries + 1):
            try:
                with urlopen(url, timeout=20) as response:
                    payload = response.read().decode("utf-8")
                break
            except HTTPError as error:
                body = error.read().decode("utf-8", errors="replace")
                message = body.strip() or error.reason
                if error.code not in {429, 500, 502, 503, 504} or attempt == self.retries:
                    raise RuntimeError(
                        f"FMP HTTP error {error.code}: {endpoint} - {message}"
                    ) from error
                time.sleep(self.retry_delay * attempt)
            except (TimeoutError, URLError) as error:
                if attempt == self.retries:
                    reason = getattr(error, "reason", error)
                    raise RuntimeError(f"FMP connection failed: {reason}") from error
                time.sleep(self.retry_delay * attempt)

        data = json.loads(payload)
        if isinstance(data, dict) and "Error Message" in data:
            raise RuntimeError(data["Error Message"])

        return data

    def first(self, endpoint, params=None):
        data = self.get(endpoint, params)
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict):
            return data

        return {}
