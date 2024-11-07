import requests

BASE_URL = "http://localhost:3333/api"

def test_get_issuers():
    url = f"{BASE_URL}/issuers"
    response = requests.get(url)
    assert response.status_code == 200
    issuers = response.json()
    assert isinstance(issuers, list)  # Assuming the response is a list of issuers