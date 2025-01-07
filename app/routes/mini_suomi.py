from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
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

@router.get("/issuers/kvk/.well-known/openid-federation")
def get_kvk_federation_statement():
    try:
        federation_statement = "eyJ0eXAiOiJlbnRpdHktc3RhdGVtZW50K2p3dCIsImp3ayI6eyJrdHkiOiJFQyIsImNydiI6IlAtMjU2IiwieCI6InZpWnczOUg1MDl4UnZaY05IdEd3OGl4RmVleGFGNExhMVpRTFpVV1RVVXMiLCJ5IjoieWROMW8wTFFBZFBUMXd2LTBiNFlCTnNtUXBjWHpmbUlLaVVoaHk0Mk1YdyIsImtpZCI6ImF1dGhlbnRpY2F0aW9uLWtleSIsImFsZyI6IkVTMjU2In0sImtpZCI6ImRpZDpqd2s6ZXlKcmRIa2lPaUpGUXlJc0ltTnlkaUk2SWxBdE1qVTJJaXdpZUNJNkluWnBXbmN6T1VnMU1EbDRVblphWTA1SWRFZDNPR2w0Um1WbGVHRkdORXhoTVZwUlRGcFZWMVJWVlhNaUxDSjVJam9pZVdST01XOHdURkZCWkZCVU1YZDJMVEJpTkZsQ1RuTnRVWEJqV0hwbWJVbExhVlZvYUhrME1rMVlkeUlzSW10cFpDSTZJbUYxZEdobGJuUnBZMkYwYVc5dUxXdGxlU0lzSW1Gc1p5STZJa1ZUTWpVMkluMCIsImFsZyI6IkVTMjU2In0.eyJpc3MiOiJkaWQ6d2ViOnRlc3QubWluaXN1b21pLmZpOmFwaTppc3N1ZXJzOmt2ayIsInN1YiI6ImRpZDp3ZWI6dGVzdC5taW5pc3VvbWkuZmk6YXBpOmlzc3VlcnM6a3ZrIiwiYXV0aG9yaXR5X2hpbnRzIjpbImh0dHBzOi8vZXdjLm9pZGYuZmluZHkuZmkiXSwiandrcyI6eyJrZXlzIjpbeyJrdHkiOiJFQyIsImNydiI6IlAtMjU2IiwieCI6InZpWnczOUg1MDl4UnZaY05IdEd3OGl4RmVleGFGNExhMVpRTFpVV1RVVXMiLCJ5IjoieWROMW8wTFFBZFBUMXd2LTBiNFlCTnNtUXBjWHpmbUlLaVVoaHk0Mk1YdyIsImtpZCI6ImF1dGhlbnRpY2F0aW9uLWtleSIsImFsZyI6IkVTMjU2In1dfX0.KNiRPvEYq3_PfNge08pMJTht2CFfZPXI3BvndIEqEXqqnfn5k5cQDNAxdQv-RUBa66vzAQHwWCFva-fZfLWeug"
        
        # Create a BytesIO object with the content
        content = BytesIO(federation_statement.encode())
        
        # Return a StreamingResponse that will trigger download
        return StreamingResponse(
            content,
            media_type="application/entity-statement+jwt",
            headers={
                "Content-Disposition": "attachment; filename=openid-federation"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/issuers/kvk/.well-known/openid-credential-configuration")
def get_credential_configuration():
    try:
        # The public key JWK from the JWT
        jwk = {
            "kty": "EC",
            "crv": "P-256",
            "x": "viZw39H509xRvZcNHtGw8ixFeexaF4La1ZQLZUWTUUs",
            "y": "ydN1o0LQAdPT1wv-0b4YBNsmQpcXzfmIKiUhhy42MXw",
            "kid": "authentication-key",
            "alg": "ES256"
        }
        
        base_url = f"{mini_suomi.ISSUER_DOMAIN}/mini-suomi"
        
        # The credential configuration response
        configuration = {
            "credential_issuer": f"{base_url}/issuers/kvk",
            "credential_endpoint": f"{base_url}/issuers/kvk/openid4vci/issue",
            "token_endpoint": f"{base_url}/token",  # Added token endpoint
            "jwks": {
                "keys": [jwk]
            }
        }
        
        return configuration
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/issuers/kvk/jwks")
def get_jwks():
    try:
        # Using the same JWK that's defined in your credential configuration
        jwk = {
            "kty": "EC",
            "crv": "P-256",
            "x": "viZw39H509xRvZcNHtGw8ixFeexaF4La1ZQLZUWTUUs",
            "y": "ydN1o0LQAdPT1wv-0b4YBNsmQpcXzfmIKiUhhy42MXw",
            "kid": "authentication-key",
            "alg": "ES256"
        }
        
        return {
            "keys": [jwk]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/credential_offer")
def get_credential_offer(id: str):
    try:
        # For now, only handle the mock offer ID
        if id != "mockOfferId123":
            raise HTTPException(status_code=404, detail="Credential offer not found")
            
        # Get base URL from environment
        base_url = f"{mini_suomi.ISSUER_DOMAIN}/mini-suomi"
        
        # Construct the credential offer metadata
        credential_offer = {
            "credential_issuer": f"{base_url}/issuers/kvk",
            "credentials": [
                {
                    "format": "vc+sd-jwt",
                    "types": ["LegalPerson"],
                    "credential_definition": {
                        "type": ["VerifiableCredential", "LegalPersonCredential"]
                    }
                }
            ],
            "grants": {
                "urn:ietf:params:oauth:grant-type:pre-authorized_code": {
                    "pre-authorized_code": "mock_pre_authorized_code_123",
                    # Optional: Require transaction code for additional security
                    # "tx_code": {
                    #     "input_mode": "numeric",
                    #     "length": 6,
                    #     "description": "Please enter the code sent to your email"
                    # }
                }
            }
        }
        
        return credential_offer
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
