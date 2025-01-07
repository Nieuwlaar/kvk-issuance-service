from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import logging
from app.services import mini_suomi

router = APIRouter()

@router.get("/.well-known/jwt-vc-issuer/mini-suomi/issuers/kvk")
async def get_jwt_vc_issuer_metadata():
    try:
        issuer_url = f"{mini_suomi.ISSUER_DOMAIN}/mini-suomi/issuers/kvk"
        
        metadata = {
            "issuer": issuer_url,
            "jwks": {
                "keys": [
                    {
                        "kid": "mini-suomi-signer-key-1",
                        "kty": "EC",
                        "crv": "P-256",
                        "x": "nUWAoAv3XZith8E7i19OdaxOLYFOwM-Z2EuM02TirT4",
                        "y": "HskHU8BjUi1U9Xqi7Swmj8gwAK_0xkcDjEW_71SosEY",
                        "alg": "ES256"
                    }
                ]
            }
        }
        
        return JSONResponse(
            content=metadata,
            media_type="application/json",
            status_code=200
        )
        
    except Exception as e:
        logging.error(f"Error generating JWT VC issuer metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 