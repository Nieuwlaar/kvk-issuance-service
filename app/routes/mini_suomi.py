from fastapi import APIRouter, HTTPException
from app.services import mini_suomi

router = APIRouter()

@router.get("/issuers")
def get_issuers():
    try:
        issuers = mini_suomi.fetch_issuers()  # Call the service function
        return issuers
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
