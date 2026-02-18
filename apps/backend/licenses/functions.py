import requests, datetime

# TODO Store API key safely
import os

ARROW_API_KEY = os.getenv("ARROW_API_KEY")
from django.conf import settings

headers = {
    "apikey": settings.ARROW_API_KEY,
    "Accept": "application/json",
}

#API_KEY = "EcghiwNIVicaxcYhWZDYJPoVlkcKZDHU"
headers = {
    "apikey": API_KEY,
    "Accept": "application/json",
}

def days_until(date_str:str) -> None:
    target = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    now = datetime.datetime.now(datetime.timezone.utc)
    delta_days = (target - now).days
    return delta_days

def get_customers():
    url = "https://xsp.arrow.com/index.php/api/customers"
    response = requests.get(url, headers=headers)
    if not response.ok:
        return {}
    return response.json()

def get_licenses(customerReference:str):
    url = f"https://xsp.arrow.com/index.php/api/v2/customers/{customerReference}/licenses"
    response = requests.get(url, headers=headers)
    if not response.ok:
        return {}
    return response.json()

def analyze_customer_licenses(customerReference:str):
    """
    Returns the list of licenses of a customer that have expired or will expire soon.
    \nThis list is sorted in ascending order.
    """
    data = get_licenses(customerReference)
    if not data:
        return False
    
    licenses = data["data"]["licenses"]
    alerts = []
    for l in licenses:
        l["daysRemaining"] = days_until(l["expiry_datetime"])
        alerts.append(l)

    return sorted(alerts, key=lambda d: d["daysRemaining"])
