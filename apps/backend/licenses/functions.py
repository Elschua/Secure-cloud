import os
import requests
import datetime

# Récupération de la clé depuis les variables d’environnement
ARROW_API_KEY = os.getenv("ARROW_API_KEY")

if not ARROW_API_KEY:
    raise RuntimeError("ARROW_API_KEY environment variable is not set")

HEADERS = {
    "apikey": ARROW_API_KEY,
    "Accept": "application/json",
}

BASE_URL = "https://xsp.arrow.com/index.php/api"


def days_until(date_str: str) -> int:
    """Return number of days until target date."""
    target = datetime.datetime.fromisoformat(
        date_str.replace("Z", "+00:00")
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    return (target - now).days


def get_customers():
    url = f"{BASE_URL}/customers"

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return {}


def get_licenses(customer_reference: str):
    url = f"{BASE_URL}/v2/customers/{customer_reference}/licenses"

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return {}


def analyze_customer_licenses(customer_reference: str):
    """
    Returns the list of licenses of a customer that have expired
    or will expire soon.
    This list is sorted in ascending order.
    """

    data = get_licenses(customer_reference)

    if not data:
        return []

    licenses = data.get("data", {}).get("licenses", [])

    alerts = []

    for license_item in licenses:
        expiry = license_item.get("expiry_datetime")
        if not expiry:
            continue

        license_item["daysRemaining"] = days_until(expiry)
        alerts.append(license_item)

    return sorted(alerts, key=lambda d: d["daysRemaining"])
