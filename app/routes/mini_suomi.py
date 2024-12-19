from fastapi import APIRouter, HTTPException
from app.services import mini_suomi

router = APIRouter()

@router.get("/issuers")
def get_issuers():
    try:
        issuers = mini_suomi.test_get_issuers()  # Call the service function
        return issuers
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/issuers/kvk/openid4vci/issue/{credentialConfiguration}/{kvkNumber}")
def issue_credential(credentialConfiguration: str, kvkNumber: str):
    try:
        result = mini_suomi.issue_credential(credentialConfiguration, kvkNumber)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
