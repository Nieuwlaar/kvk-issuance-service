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

# Pydantic model for natural person company certificate request
class NaturalPersonCompanyCertificateRequest(BaseModel):
    givenName: str
    familyName: str
    birthdate: str  # Format: "YYYY-MM-DD" (ISO format)

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

@router.post("/natural-person/company-certificate")
async def get_natural_person_company_certificate(request: NaturalPersonCompanyCertificateRequest):
    """Proxy endpoint for getting company certificates associated with a natural person"""
    try:
        return KVKBevoegdhedenAPI.get_natural_person_company_certificate(
            given_name=request.givenName,
            family_name=request.familyName,
            birthdate=request.birthdate
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
