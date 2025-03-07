import requests
import logging
from app.clients.kvk_bevoegdheden_rest_api import KVKBevoegdhedenAPI
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from typing import Dict, Any
from jose import jwt
import hashlib
import json
import base64

# Load environment variables
load_dotenv()

# Get ISSUER_DOMAIN based on environment
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
ISSUER_DOMAIN = os.getenv('PROD_DOMAIN') if ENVIRONMENT == "production" else os.getenv('DEV_DOMAIN')

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# def test_get_issuers():
#     url = f"{BASE_URL}/issuers"
#     response = requests.get(url)
#     assert response.status_code == 200
#     issuers = response.json()
#     return issuers

def issue_credential(credentialConfiguration: str, kvkNumber: str):
    print(f"credentialConfiguration: {credentialConfiguration}")
    try:
        # Get LPID or company data based on credential configuration
        now = datetime.utcnow()
        one_year_from_now = now + timedelta(days=365)
        
        if credentialConfiguration == "LPIDSdJwt":
            # lpid_data = KVKBevoegdhedenAPI.get_lpid(kvkNumber)
            # payload = {
            #     "legal_person_id": lpid_data["data"]["id"],
            #     "legal_person_name": lpid_data["data"]["legal_person_name"],
            #     "issuer_id": lpid_data["metadata"]["issuer_id"],
            #     "issuer_name": lpid_data["metadata"]["issuing_authority_name"],
            #     "issuer_country": lpid_data["metadata"]["issuing_country"],
            #     "issuance_date": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            #     "expiry_date": one_year_from_now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            #     "credential_status": "active",
            #     "authentic_source_id": lpid_data["metadata"]["issuer_id"],
            #     "authentic_source_name": "Kamer van Koophandel"
            # }
            offer_id = "mockOfferId123"  # Generate a unique ID if necessary
            credential_offer_url = f"{ISSUER_DOMAIN}/mini-suomi/credential_offer?id={offer_id}"

            # Construct the credential offer URI
            credential_offer_uri = f"openid-credential-offer://?credential_offer_uri={requests.utils.quote(credential_offer_url)}"

            # Return the credential offer URI
            return {"credential_offer_uri": credential_offer_uri}
        
        elif credentialConfiguration == "EUCCSdJwt":
            # company_data = KVKBevoegdhedenAPI.get_company_certificate(kvkNumber)
            # legal_representatives = [
            #     {
            #         "role": "J",
            #         "legalEntityId": company_data["data"]["registration_number"],
            #         "scopeOfRepresentation": "Jointly",
            #         "family_name": person["full_name"].split()[-1],
            #         "given_name": " ".join(person["full_name"].split()[:-1]),
            #         "birth_date": datetime.strptime(person["date_of_birth"], "%d-%m-%Y").strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            #     }
            #     for person in company_data["data"]["authorized_persons"]
            # ]
            # address_parts = company_data["data"]["postal_address"].split()
            # postal_code = next((part for part in address_parts if len(part) == 6 and part[:4].isdigit()), "")
            
            # payload = {
            #     "legalName": company_data["data"]["legal_person_name"],
            #     "legalFormType": company_data["data"]["legal_form"],
            #     "legalIdentifier": company_data["data"]["id"],
            #     "registeredAddress": {
            #         "post_code": postal_code,
            #         "post_name": address_parts[-1] if address_parts else "",
            #         "thoroughfare": " ".join(address_parts[:-1]) if address_parts else ""
            #     },
            #     "postalAddress": {
            #         "post_code": postal_code,
            #         "post_name": address_parts[-1] if address_parts else "",
            #         "thoroughfare": " ".join(address_parts[:-1]) if address_parts else ""
            #     },
            #     "registrationDate": datetime.strptime(company_data["data"]["date_of_registration"], "%d-%m-%Y").strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            #     "legalEntityStatus": "active",
            #     "legalRepresentative": legal_representatives,
            #     "legalEntityActivity": [{"code": "", "businessDescription": ""}],
            #     "contactPoint": {
            #         "contactPage": "",
            #         "hasEmail": company_data["data"]["electronic_address"],
            #         "hasTelephone": ""
            #     },
            #     "issuer_id": company_data["metadata"]["issuer_id"],
            #     "issuer_name": company_data["metadata"]["issuing_authority_name"],
            #     "issuer_country": company_data["metadata"]["issuing_country"],
            #     "issuance_date": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            #     "expiry_date": one_year_from_now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            #     "authentic_source_id": company_data["metadata"]["issuer_id"],
            #     "authentic_source_name": "Kamer van Koophandel"
            # }
                    # Construct the credential offer URL (this can point to an internal or mock endpoint)
            offer_id = "mockOfferId124"  # Generate a unique ID if necessary
            credential_offer_url = f"{ISSUER_DOMAIN}/mini-suomi/credential_offer?id={offer_id}"

            # Construct the credential offer URI
            credential_offer_uri = f"openid-credential-offer://?credential_offer_uri={requests.utils.quote(credential_offer_url)}"

            # Return the credential offer URI
            return {"credential_offer_uri": credential_offer_uri}
        else:
            raise ValueError(f"Unsupported credential configuration: {credentialConfiguration}")



    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        raise Exception(f"Request failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise

def generate_credential_jwt(credential_type: str, kvk_number: str) -> str:
    try:
        now = datetime.utcnow()
        one_year_from_now = now + timedelta(days=365)

        if credential_type == "LPIDSdJwt":
            lpid_data = KVKBevoegdhedenAPI.get_lpid(kvk_number)
            
            # Create disclosure objects with salt
            disclosures = []
            sd_hashes = []
            
            claims = {
                "legal_person_id": lpid_data["data"]["id"],
                "legal_person_name": lpid_data["data"]["legal_person_name"],
                "issuer_id": lpid_data["metadata"]["issuer_id"],
                "issuer_name": lpid_data["metadata"]["issuing_authority_name"],
                "issuer_country": lpid_data["metadata"]["issuing_country"],
                "issuance_date": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "expiry_date": one_year_from_now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "credential_status": "active",
                "authentic_source_id": lpid_data["metadata"]["issuer_id"],
                "authentic_source_name": "Kamer van Koophandel",
                # "authentic_source_name2": "Kamer van Koophandel",
            }

            # Generate salted disclosures for each claim
            for key, value in claims.items():
                # Log each claim being processed
                logging.info(f"Processing claim: {key} with value: {value}")
                
                # Generate random salt
                salt = base64.urlsafe_b64encode(os.urandom(16)).decode('utf-8').rstrip('=')
                
                # Create disclosure array [salt, key, value]
                disclosure = [salt, key, value]
                
                # Convert to JSON and then base64url encode
                disclosure_json = json.dumps(disclosure, separators=(',', ':'))
                disclosure_b64 = base64.urlsafe_b64encode(
                    disclosure_json.encode('utf-8')
                ).decode('utf-8').rstrip('=')
                
                # Log the disclosure details
                logging.info(f"Generated disclosure for {key}:")
                logging.info(f"  Raw disclosure: {disclosure}")
                logging.info(f"  Encoded disclosure: {disclosure_b64}")
                
                # Add encoded disclosure to list
                disclosures.append(disclosure_b64)
                
                # Generate hash for _sd array
                hash_obj = hashlib.sha256(disclosure_json.encode('utf-8'))
                sd_hash = base64.urlsafe_b64encode(hash_obj.digest()).decode('utf-8').rstrip('=')
                sd_hashes.append(sd_hash)
                
                # Log the hash
                logging.info(f"  Generated hash: {sd_hash}")

            # Log final arrays
            logging.info("=== Final Arrays ===")
            logging.info(f"Number of claims: {len(claims)}")
            logging.info(f"Number of disclosures: {len(disclosures)}")
            logging.info(f"Number of hashes: {len(sd_hashes)}")
            logging.info(f"All claims keys: {list(claims.keys())}")
            logging.info(f"All disclosure decoded: {[json.loads(base64.urlsafe_b64decode(d + '==').decode('utf-8')) for d in disclosures]}")

            # JWT header with embedded JWK
            headers = {
                "alg": "ES256",
                "typ": "vc+sd-jwt",
                "kid": "authentication-key",
                "jwk": {
                    "kty": "EC",
                    "crv": "P-256",
                    "x": "viZw39H509xRvZcNHtGw8ixFeexaF4La1ZQLZUWTUUs",
                    "y": "ydN1o0LQAdPT1wv-0b4YBNsmQpcXzfmIKiUhhy42MXw",
                    "alg": "ES256",
                    "kid": "authentication-key"
                    # "use": "sig"
                }
            }

            # JWT payload
            jwt_payload = {
                "iat": int(now.timestamp()),
                "nbf": int(now.timestamp()) - 2963,
                "vct": "LPID",
                "iss": "https://kvk-issuance-service.nieuwlaar.com/mini-suomi/issuers/kvk",
                "_sd": sd_hashes,
                "_sd_alg": "sha-256",
                "cnf": {
                    "jwk": {
                        "kty": "EC",
                        "x": "rYmxB0Pftb6Vg2hqDw5bt9ZmunVU8cr5Q0YAKlkIXmQ",
                        "y": "QkAPrZ5JQUPBKnodOefFDJRYu54hk-6toTFngyEAEP8",
                        "crv": "P-256",
                        "kid": "authentication-key",
                        "alg": "ES256"
                    }
                },
                "termsOfUse": []
            }

            # Hardcoded private key for signing
            private_key = {
                "kty": "EC",
                "crv": "P-256",
                "x": "viZw39H509xRvZcNHtGw8ixFeexaF4La1ZQLZUWTUUs",
                "y": "ydN1o0LQAdPT1wv-0b4YBNsmQpcXzfmIKiUhhy42MXw",
                "alg": "ES256",
                "kid": "authentication-key",
                "d": "kAP-MAxRTy4F77xl-9unD-9IWfneEMC7j6E4WdSEdxI"
                # "use": "sig"
            }

            # Generate the JWT
            credential_jwt = jwt.encode(
                claims=jwt_payload,
                key=private_key,
                algorithm="ES256",
                headers=headers
            )

            # Combine JWT and base64url-encoded disclosures
            combined_token = credential_jwt + "~" + "~".join(disclosures) + "~"

            logging.info("=== SD-JWT Generation Details ===")
            logging.info(f"Headers: {headers}")
            logging.info(f"Payload: {jwt_payload}")
            logging.info(f"Disclosures (decoded): {[json.loads(base64.urlsafe_b64decode(d + '==').decode('utf-8')) for d in disclosures]}")
            logging.info(f"Final SD-JWT: {combined_token}")
            
            # Add this debug logging
            logging.info("=== SD-JWT Debug Information ===")
            logging.info(f"JWT part length: {len(credential_jwt)}")
            logging.info(f"Number of disclosures: {len(disclosures)}")
            logging.info("Individual disclosures:")
            for i, disc in enumerate(disclosures):
                # Decode and print each disclosure
                padded = disc + "=" * (-len(disc) % 4)
                decoded = json.loads(base64.urlsafe_b64decode(padded))
                logging.info(f"Disclosure {i+1}: {decoded}")
            logging.info(f"Final token parts: {len(combined_token.split('~'))}")
            logging.info("=== End Debug Information ===")
            
            return combined_token

        elif credential_type == "EUCCSdJwt":
            company_data = KVKBevoegdhedenAPI.get_company_certificate(kvk_number)
            
            # Create disclosure objects with salt
            disclosures = []
            sd_hashes = []
            
            # Prepare legal representatives data
            legal_representatives = [
                {
                    "role": "J",
                    "legalEntityId": company_data["data"]["registration_number"],
                    "scopeOfRepresentation": "Jointly",
                    "family_name": person["full_name"].split()[-1],
                    "given_name": " ".join(person["full_name"].split()[:-1]),
                    "birth_date": datetime.strptime(person["date_of_birth"], "%d-%m-%Y").strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                }
                for person in company_data["data"]["authorized_persons"]
            ]

            # Parse address
            address_parts = company_data["data"]["postal_address"].split()
            postal_code = next((part for part in address_parts if len(part) == 6 and part[:4].isdigit()), "")
            post_name = address_parts[-1] if address_parts else ""
            thoroughfare = " ".join(address_parts[:-1]) if address_parts else ""

            # Prepare claims
            claims = {
                "legalName": company_data["data"]["legal_person_name"],
                "legalFormType": company_data["data"]["legal_form"],
                "legalIdentifier": company_data["data"]["id"],
                "registeredAddress": {
                    "post_code": postal_code,
                    "post_name": post_name,
                    "thoroughfare": thoroughfare
                },
                "postalAddress": {
                    "post_code": postal_code,
                    "post_name": post_name,
                    "thoroughfare": thoroughfare
                },
                "registrationDate": datetime.strptime(company_data["data"]["date_of_registration"], "%d-%m-%Y").strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "shareCapital": None,
                "legalEntityStatus": "active",
                "legalRepresentative": legal_representatives,
                "legalEntityActivity": [{"code": "", "businessDescription": ""}],
                "contactPoint": {
                    "contactPage": "",
                    "hasEmail": company_data["data"]["electronic_address"],
                    "hasTelephone": ""
                },
                "issuer_id": company_data["metadata"]["issuer_id"],
                "issuer_name": company_data["metadata"]["issuing_authority_name"],
                "issuer_country": company_data["metadata"]["issuing_country"],
                "issuance_date": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "expiry_date": one_year_from_now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "authentic_source_id": company_data["metadata"]["issuer_id"],
                "authentic_source_name": "Kamer van Koophandel",
                # "authentic_source_name2": "Kamer van Koophandel",
            }

            # Generate salted disclosures for each claim
            for key, value in claims.items():
                # Generate random salt
                salt = base64.urlsafe_b64encode(os.urandom(16)).decode('utf-8').rstrip('=')
                
                # Create disclosure array [salt, key, value]
                disclosure = [salt, key, value]
                
                # Convert to JSON and then base64url encode
                disclosure_json = json.dumps(disclosure, separators=(',', ':'))
                disclosure_b64 = base64.urlsafe_b64encode(
                    disclosure_json.encode('utf-8')
                ).decode('utf-8').rstrip('=')
                
                # Add encoded disclosure to list
                disclosures.append(disclosure_b64)
                
                # Generate hash for _sd array
                hash_obj = hashlib.sha256(disclosure_json.encode('utf-8'))
                sd_hash = base64.urlsafe_b64encode(hash_obj.digest()).decode('utf-8').rstrip('=')
                sd_hashes.append(sd_hash)

            # JWT header with embedded JWK
            headers = {
                "alg": "ES256",
                "typ": "vc+sd-jwt",
                "kid": "authentication-key",
                "jwk": {
                    "kty": "EC",
                    "crv": "P-256",
                    "x": "viZw39H509xRvZcNHtGw8ixFeexaF4La1ZQLZUWTUUs",
                    "y": "ydN1o0LQAdPT1wv-0b4YBNsmQpcXzfmIKiUhhy42MXw",
                    "alg": "ES256",
                    "kid": "authentication-key"
                    # "use": "sig"
                }
            }

            # JWT payload
            jwt_payload = {
                "iat": int(now.timestamp()),
                "nbf": int(now.timestamp()) - 2963,
                "vct": "EUCC",  # Changed to EUCC for this credential type
                "iss": "https://kvk-issuance-service.nieuwlaar.com/mini-suomi/issuers/kvk",
                "_sd": sd_hashes,
                "_sd_alg": "sha-256",
                "cnf": {
                    "jwk": {
                        "kty": "EC",
                        "x": "rYmxB0Pftb6Vg2hqDw5bt9ZmunVU8cr5Q0YAKlkIXmQ",
                        "y": "QkAPrZ5JQUPBKnodOefFDJRYu54hk-6toTFngyEAEP8",
                        "crv": "P-256",
                        "kid": "authentication-key",
                        "alg": "ES256"
                    }
                },
                "termsOfUse": []
            }

            # Use the same private key and JWT generation as before
            private_key = {
                "kty": "EC",
                "crv": "P-256",
                "x": "viZw39H509xRvZcNHtGw8ixFeexaF4La1ZQLZUWTUUs",
                "y": "ydN1o0LQAdPT1wv-0b4YBNsmQpcXzfmIKiUhhy42MXw",
                "alg": "ES256",
                "kid": "authentication-key",
                "d": "kAP-MAxRTy4F77xl-9unD-9IWfneEMC7j6E4WdSEdxI"
                # "use": "sig"
            }

            # Generate the JWT
            credential_jwt = jwt.encode(
                claims=jwt_payload,
                key=private_key,
                algorithm="ES256",
                headers=headers
            )

            # Combine JWT and base64url-encoded disclosures
            combined_token = credential_jwt + "~" + "~".join(disclosures) + "~"

            # Add this debug logging
            logging.info("=== SD-JWT Debug Information ===")
            logging.info(f"JWT part length: {len(credential_jwt)}")
            logging.info(f"Number of disclosures: {len(disclosures)}")
            logging.info("Individual disclosures:")
            for i, disc in enumerate(disclosures):
                # Decode and print each disclosure
                padded = disc + "=" * (-len(disc) % 4)
                decoded = json.loads(base64.urlsafe_b64decode(padded))
                logging.info(f"Disclosure {i+1}: {decoded}")
            logging.info(f"Final token parts: {len(combined_token.split('~'))}")
            logging.info("=== End Debug Information ===")
            
            return combined_token

    except Exception as e:
        logging.error(f"Error generating credential JWT: {str(e)}")
        raise


