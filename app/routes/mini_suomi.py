from fastapi import APIRouter, HTTPException, Form, Request
from fastapi.responses import StreamingResponse, JSONResponse
from io import BytesIO
from app.services import mini_suomi
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from fastapi import Header
import logging

router = APIRouter()

# Create a separate router for .well-known endpoints
well_known_router = APIRouter()

class ProofObject(BaseModel):
    proof_type: str
    jwt: Optional[str] = None
    ldp_vp: Optional[Dict[str, Any]] = None
    attestation: Optional[str] = None

class CredentialRequest(BaseModel):
    format: Optional[str] = None
    types: Optional[List[str]] = None
    proof: Optional[ProofObject] = None
    proofs: Optional[Dict[str, list]] = None
    credential_response_encryption: Optional[Dict[str, Any]] = None

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
        if id == "mockOfferId123":

            # Get base URL from environment
            base_url = f"{mini_suomi.ISSUER_DOMAIN}/mini-suomi"
            
            # Construct the credential offer metadata
            credential_offer = {
                "credential_issuer": f"{base_url}/issuers/kvk",
                # Add credentials array as required by the spec
                "credentials": [{
                    "format": "vc+sd-jwt",
                    "types": ["LPIDSdJwt"],
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
        if id == "mockOfferId124":
            # Get base URL from environment
            base_url = f"{mini_suomi.ISSUER_DOMAIN}/mini-suomi"
            
            # Construct the credential offer metadata
            credential_offer = {
                "credential_issuer": f"{base_url}/issuers/kvk",
                # Add credentials array as required by the spec
                "credentials": [{
                    "format": "vc+sd-jwt",
                    "types": ["EUCCSdJwt"],
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
        else:
            raise HTTPException(status_code=404, detail="Credential offer not found")
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
                },
                "EUCCSdJwt": {
                    "format": "vc+sd-jwt",
                    "scope": "EUCCSdJwt",
                    "cryptographic_binding_methods_supported": ["jwk"],
                    "credential_signing_alg_values_supported": ["ES256"],
                    "proof_types_supported": {
                        "jwt": {
                            "proof_signing_alg_values_supported": ["ES256"]
                        }
                    },
                    "display": [{
                        "name": "EU Company Certificate",
                        "locale": "en-US",
                        "logo": {
                            "uri": "https://example.com/logo.png",
                            "alt_text": "EU Company Certificate logo"
                        },
                        "background_color": "#12107c",
                        "text_color": "#FFFFFF"
                    }],
                    "claims": [
                        {
                            "path": ["legal_person_name"],
                            "display": [{
                                "name": "Legal Entity Name",
                                "locale": "en-US"
                            }]
                        },
                        {
                            "path": ["legal_person_id"],
                            "display": [{
                                "name": "Legal Entity ID",
                                "locale": "en-US"
                            }]
                        },
                        {
                            "path": ["legal_form_type"],
                            "display": [{
                                "name": "Legal Form",
                                "locale": "en-US"
                            }]
                        },
                        {
                            "path": ["registration_member_state"],
                            "display": [{
                                "name": "Registration Member State",
                                "locale": "en-US"
                            }]
                        },
                        {
                            "path": ["registered_address", "full_address"],
                            "display": [{
                                "name": "Registered Address",
                                "locale": "en-US"
                            }]
                        },
                        {
                            "path": ["registration_date"],
                            "display": [{
                                "name": "Registration Date",
                                "locale": "en-US"
                            }]
                        },
                        {
                            "path": ["legal_entity_status"],
                            "display": [{
                                "name": "Legal Entity Status",
                                "locale": "en-US"
                            }]
                        },
                        {
                            "path": ["legal_entity_activity"],
                            "display": [{
                                "name": "Main Activities",
                                "locale": "en-US"
                            }]
                        },
                        {
                            "path": ["share_capital"],
                            "display": [{
                                "name": "Share Capital",
                                "locale": "en-US"
                            }]
                        },
                        {
                            "path": ["legal_entity_duration"],
                            "display": [{
                                "name": "Company Duration",
                                "locale": "en-US"
                            }]
                        },
                        {
                            "path": ["contact_point", "contact_email"],
                            "display": [{
                                "name": "Contact Email",
                                "locale": "en-US"
                            }]
                        },
                        {
                            "path": ["contact_point", "contact_telephone"],
                            "display": [{
                                "name": "Contact Telephone",
                                "locale": "en-US"
                            }]
                        },
                        {
                            "path": ["contact_point", "contact_page"],
                            "display": [{
                                "name": "Website",
                                "locale": "en-US"
                            }]
                        },
                        {
                            "path": ["legal_representative"],
                            "display": [{
                                "name": "Legal Representatives",
                                "locale": "en-US"
                            }],
                            "mandatory": true
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

@router.post("/issuers/kvk/token")
async def token_endpoint(
    grant_type: str = Form(...),
    pre_authorized_code: Optional[str] = Form(None, alias="pre-authorized_code"),
    tx_code: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    authorization_details: Optional[str] = Form(None)
):
    try:
        # Validate grant type
        if grant_type != "urn:ietf:params:oauth:grant-type:pre-authorized_code":
            return JSONResponse(
                status_code=400,
                content={
                    "error": "unsupported_grant_type",
                    "error_description": "Only pre-authorized code grant type is supported"
                }
            )
        
        # Validate pre-authorized code
        if not pre_authorized_code or pre_authorized_code != "mock_pre_authorized_code_123":
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_grant",
                    "error_description": "Invalid or expired pre-authorized code"
                }
            )
            
        # For now, we'll create a simple response with a mock access token
        response = {
            "access_token": "mock_access_token_456",
            "token_type": "Bearer",
            "expires_in": 3600,
            "authorization_details": [{
                "type": "openid_credential",
                "credential_configuration_id": "LPIDSdJwt",
                "credential_identifiers": ["mock_credential_id_789"]
            }]
        }
        
        return JSONResponse(
            content=response,
            media_type="application/json",
            headers={"Cache-Control": "no-store"}
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": "server_error",
                "error_description": str(e)
            }
        )

@router.post("/issuers/kvk/openid4vci/issue")
async def issue_credential_endpoint(
    request_body: CredentialRequest,
    request: Request,
    authorization: str = Header(None)
):
    try:
        # Log full request details
        body = await request.json()
        logging.info("=== Credential Request Details ===")
        logging.info(f"Request Body: {body}")
        logging.info(f"Authorization: {authorization}")
        logging.info(f"Headers: {dict(request.headers)}")
        
        # Validate authorization token
        if not authorization or not authorization.startswith("Bearer "):
            logging.error("Missing or invalid authorization token")
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_token"},
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Log parsed request body
        logging.info(f"Parsed Request Body: {request_body}")

        # Validate format and types
        if request_body.format != "vc+sd-jwt":
            logging.error(f"Unsupported format: {request_body.format}")
            return JSONResponse(
                status_code=400,
                content={
                    "error": "unsupported_credential_format",
                    "error_description": "Only vc+sd-jwt format is supported"
                }
            )

        if not request_body.types or not any(cred_type in request_body.types for cred_type in ["LPIDSdJwt", "EUCCSdJwt"]):
            logging.error(f"Invalid types: {request_body.types}")
            return JSONResponse(
                status_code=400,
                content={
                    "error": "unsupported_credential_type",
                    "error_description": "Either LPIDSdJwt or EUCCSdJwt type is required"
                }
            )

        # Generate actual JWT credential
        if "LPIDSdJwt" in request_body.types:
            credential_jwt = mini_suomi.generate_credential_jwt(
                credential_type="LPIDSdJwt",  # or "EUCCSdJwt" based on request
                kvk_number="90000011"  # Get this from the request or context
            )
        elif "EUCCSdJwt" in request_body.types:
            credential_jwt = mini_suomi.generate_credential_jwt(
                credential_type="EUCCSdJwt",  # or "EUCCSdJwt" based on request
                kvk_number="90000011"  # Get this from the request or context
            )

        # Format response
        response = {
            "format": "vc+sd-jwt",
            "credential": credential_jwt,
            "c_nonce": "xyz123",
            "c_nonce_expires_in": 3600
        }
        
        logging.info(f"Sending response: {response}")
        return JSONResponse(
            content=response,
            media_type="application/json",
            headers={"Cache-Control": "no-store"}
        )

    except Exception as e:
        logging.error(f"Error in credential issuance: {str(e)}")
        logging.error(f"Exception details:", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "invalid_credential_request",
                "error_description": str(e)
            }
        )

@well_known_router.get("/.well-known/jwt-vc-issuer/mini-suomi/issuers/kvk")
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
                    "kid": "authentication-key",
                    "use": "sig"
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
