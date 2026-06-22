import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


BASE_URL = "https://financialmodelingprep.com/stable"


class FmpClient:
    def __init__(self, api_key):
        self.api_key = api_key

    def get(self, endpoint, params=None):
        query = {"apikey": self.api_key}
        if params:
            query.update(params)

        url = f"{BASE_URL}/{endpoint}?{urlencode(query)}"

        try:
            with urlopen(url, timeout=20) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            message = body.strip() or error.reason
            raise RuntimeError(
                f"FMP HTTP error {error.code}: {endpoint} - {message}"
            ) from error
        except URLError as error:
            raise RuntimeError(f"FMP connection failed: {error.reason}") from error

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
