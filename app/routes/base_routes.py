from fastapi import APIRouter, HTTPException
from app.clients.kvk_bevoegdheden_rest_api import KVKBevoegdhedenAPI

# Create a router instance
router = APIRouter()

# Define a simple GET route at the root
@router.get("/")
def root():
    return {"message": "Welcome to the KVK Issuance Service!"}

# Route for fetching LPID details (Use this to test the connection with the kvk-bevoegdheden-rest-api)
@router.get("/lpid/{kvk_nummer}")
def get_lpid(kvk_nummer: str):
    """
    Fetches the Legal Person Identification Data (LPID) details for the specified KVK number.
    """
    try:
        lpid_data = KVKBevoegdhedenAPI.get_lpid(kvk_nummer)
        return lpid_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
