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
                        "kty": "EC",
                        "crv": "P-256",
                        "x": "viZw39H509xRvZcNHtGw8ixFeexaF4La1ZQLZUWTUUs",
                        "y": "ydN1o0LQAdPT1wv-0b4YBNsmQpcXzfmIKiUhhy42MXw",
                        "alg": "ES256",
                        "kid": "authentication-key"
                        # "use": "sig"
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