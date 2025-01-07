from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
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
            # Add credentials array as required by the spec
            "credentials": [{
                "format": "vc+sd-jwt",
                "types": ["LegalPerson"],
                "trust_framework": {
                    "name": "kvk",
                    "type": "Legal Entity",
                    "uri": f"{base_url}/issuers/kvk"
                }
            }],
            "grants": {
                "urn:ietf:params:oauth:grant-type:pre-authorized_code": {
                    "pre-authorized_code": "mock_pre_authorized_code_123"
                }
            }
        }
        
        # Set correct content type
        return JSONResponse(
            content=credential_offer,
            media_type="application/json"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/issuers/kvk/.well-known/openid-credential-issuer")
def get_credential_issuer_metadata():
    try:
        base_url = f"{mini_suomi.ISSUER_DOMAIN}/mini-suomi"
        
        metadata = {
            "credential_issuer": f"{base_url}/issuers/kvk",
            "credential_endpoint": f"{base_url}/issuers/kvk/openid4vci/issue",
            "token_endpoint": f"{base_url}/token",
            "credential_configurations_supported": {
                "LPIDSdJwt": {
                    "format": "vc+sd-jwt",
                    "scope": "LPIDSdJwt",
                    "cryptographic_binding_methods_supported": ["jwk"],
                    "credential_signing_alg_values_supported": ["ES256"],
                    "proof_types_supported": {
                        "jwt": {
                            "proof_signing_alg_values_supported": ["ES256"]
                        }
                    },
                    "display": [{
                        "name": "Legal Person Identifier",
                        "locale": "en-US",
                        "logo": {
                            "uri": "https://example.com/logo.png",
                            "alt_text": "Legal Person ID logo"
                        },
                        "background_color": "#12107c",
                        "text_color": "#FFFFFF"
                    }],
                    "claims": [
                        {
                            "path": ["legal_person_id"],
                            "display": [{
                                "name": "Legal Person ID",
                                "locale": "en-US"
                            }]
                        },
                        {
                            "path": ["legal_person_name"],
                            "display": [{
                                "name": "Legal Person Name",
                                "locale": "en-US"
                            }]
                        }
                    ]
                }
            }
        }
        
        # Return with correct content type
        return JSONResponse(
            content=metadata,
            media_type="application/json",
            headers={"Content-Language": "en-US"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/issuers/kvk/.well-known/oauth-authorization-server")
def get_oauth_server_metadata():
    try:
        base_url = f"{mini_suomi.ISSUER_DOMAIN}/mini-suomi"
        issuer_url = f"{base_url}/issuers/kvk"
        
        metadata = {
            "issuer": issuer_url,
            "authorization_endpoint": f"{issuer_url}/authorize",
            "token_endpoint": f"{issuer_url}/token",
            "jwks_uri": f"{issuer_url}/jwks.json",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "urn:ietf:params:oauth:grant-type:pre-authorized_code"],
            "token_endpoint_auth_methods_supported": ["none"],
            "credential_endpoint": f"{issuer_url}/openid4vci/issue",
            "credential_configurations_supported": {
                "LPIDSdJwt": {
                    "format": "vc+sd-jwt",
                    "cryptographic_binding_methods_supported": ["jwk"],
                    "credential_signing_alg_values_supported": ["ES256"],
                    "proof_types_supported": {
                        "jwt": {
                            "proof_signing_alg_values_supported": ["ES256"]
                        }
                    }
                }
            }
        }
        
        return JSONResponse(
            content=metadata,
            media_type="application/json",
            headers={"Content-Language": "en-US"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
