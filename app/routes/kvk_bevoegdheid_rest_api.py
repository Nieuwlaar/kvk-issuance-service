from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date

from app.clients.kvk_bevoegdheden_rest_api import KVKBevoegdhedenAPI

router = APIRouter()

# Pydantic model for signatory rights request
class SignatoryRightsRequest(BaseModel):
    geslachtsnaam: str
    voornamen: str
    geboortedatum: str  # Format: "DD-MM-YYYY"
    voorvoegselGeslachtsnaam: Optional[str] = ""

@router.get("/lpid/{kvk_nummer}")
async def get_lpid(kvk_nummer: str):
    """Proxy endpoint for getting LPID details"""
    try:
        return KVKBevoegdhedenAPI.get_lpid(kvk_nummer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/company-certificate/{kvk_nummer}")
async def get_company_certificate(kvk_nummer: str):
    """Proxy endpoint for getting company certificate"""
    try:
        return KVKBevoegdhedenAPI.get_company_certificate(kvk_nummer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/signatory-rights/{kvk_nummer}")
async def check_signatory_right(kvk_nummer: str, request: SignatoryRightsRequest):
    """Proxy endpoint for checking signatory rights"""
    try:
        return KVKBevoegdhedenAPI.check_signatory_right(
            kvk_nummer=kvk_nummer,
            geslachtsnaam=request.geslachtsnaam,
            voornamen=request.voornamen,
            geboortedatum=request.geboortedatum,
            voorvoegselGeslachtsnaam=request.voorvoegselGeslachtsnaam
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
