import base64
import json
from cryptography.hazmat.primitives.asymmetric.ec import ECDSA, SECP256R1
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.hashes import SHA256

def base64url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

# Load private key
with open("private_key.pem", "rb") as f:
    private_key = load_pem_private_key(f.read(), password=None)

# Header and payload
header = {
    "typ": "entity-statement+jwt",
    "jwk": {
        "kty": "EC",
        "crv": "P-256",
        "x": "viZw39H509xRvZcNHtGw8ixFeexaF4La1ZQLZUWTUUs",
        "y": "ydN1o0LQAdPT1wv-0b4YBNsmQpcXzfmIKiUhhy42MXw",
        "kid": "authentication-key",
        "alg": "ES256"
    },
    "alg": "ES256"
}
payload = {
    "iss": "did:web:test.minisuomi.fi:api:issuers:kvk",
    "sub": "did:web:test.minisuomi.fi:api:issuers:kvk",
    "authority_hints": ["https://ewc.oidf.findy.fi"],
    "jwks": {
        "keys": [
            {
                "kty": "EC",
                "crv": "P-256",
                "x": "viZw39H509xRvZcNHtGw8ixFeexaF4La1ZQLZUWTUUs",
                "y": "ydN1o0LQAdPT1wv-0b4YBNsmQpcXzfmIKiUhhy42MXw",
                "kid": "authentication-key",
                "alg": "ES256"
            }
        ]
    }
}

# Encode header and payload
encoded_header = base64url_encode(json.dumps(header).encode())
encoded_payload = base64url_encode(json.dumps(payload).encode())
signing_input = f"{encoded_header}.{encoded_payload}"

# Sign the JWT
signature = private_key.sign(signing_input.encode(), ECDSA(SHA256()))
encoded_signature = base64url_encode(signature)

# Create the JWT
jwt_token = f"{signing_input}.{encoded_signature}"
print("Generated JWT:")
print(jwt_token)
