import jwt
import datetime

# Private key details
private_key = {
    "kty": "EC",
    "crv": "P-256",
    "x": "OIL1lFDz9Y1wYvijS_VjwTRd6PdIVNQS-fpbgip5sIM",
    "y": "qYktTDnYez5RdLtH8XNrX5vLx8a_5paUCpkbc-6yBbg",
    "d": "45jiPQAKLbueMORqF_V3Dhi4PlnDQgXM3SaTqsOlfQI",
    "kid": "authentication-key",
    "alg": "ES256"
}

# JWT payload
payload = {
    "iss": "https://example.commmm",  # Issuer
    "sub": "user-id",             # Subject (user ID)
    "aud": "https://test.minisuomi.fi/api",  # Audience (API endpoint)
    "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),  # Expiration time
    "iat": datetime.datetime.utcnow(),  # Issued at
    "scopes": ["issuers", "holders"]    # Custom claims/scopes
}

# Convert the private key into a usable format
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import load_pem_private_key, Encoding, NoEncryption

private_key_obj = ec.derive_private_key(
    int(private_key["d"], 16),
    curve=SECP256R1(),
    backend=None
)

# Create the signed JWT
jwt_token = jwt.encode(
    payload,
    private_key_obj,
    algorithm="ES256",
    headers={"kid": private_key["kid"]}
)

print("Generated JWT:", jwt_token)
