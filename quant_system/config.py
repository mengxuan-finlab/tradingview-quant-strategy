import os


def get_fmp_api_key():
    api_key = os.getenv("FMP_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "Missing FMP_API_KEY. Set it in PowerShell with: "
            "$env:FMP_API_KEY='your_api_key'"
        )

    return api_key
