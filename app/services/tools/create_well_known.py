from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key,
    Encoding,
    PublicFormat,
)
from cryptography.exceptions import InvalidSignature
import base64
import json

# Utility function for Base64Url encoding
def base64url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

# Load the private key from a file
private_key_path = "private_key.pem"
with open(private_key_path, "rb") as key_file:
    private_key_pem = key_file.read()

# Load the private key
private_key = load_pem_private_key(private_key_pem, password=None)

# Derive the public key from the private key
public_key = private_key.public_key()
public_key_numbers = public_key.public_numbers()

# Extract `x` and `y` for JWK from the public key
x = base64url_encode(public_key_numbers.x.to_bytes(32, "big"))
y = base64url_encode(public_key_numbers.y.to_bytes(32, "big"))

# Public key details for JWK
jwk = {
    'kty': 'EC',
    'crv': 'P-256',
    'x': x,
    'y': y,
    "kid": "authentication-key",
    'alg': 'ES256'
}

# Create kid from jwk
jwk_for_kid = {k: v for k, v in jwk.items()}  # Create copy without 'kid'
jwk_json = json.dumps(jwk_for_kid, separators=(',', ':'))
jwk_base64url = base64url_encode(jwk_json.encode())
kid = f"did:jwk:{jwk_base64url}"

# Add kid to jwk
jwk['kid'] = 'authentication-key'

# Entity statement payload
entity_statement = {
    "iss": "did:web:test.minisuomi.fi:api:issuers:kvk",
    "sub": "did:web:test.minisuomi.fi:api:issuers:kvk",
    "authority_hints": ["https://ewc.oidf.findy.fi"],
    "jwks": {"keys": [jwk]},
}

# Add the custom header with `typ` and `jwk`
header = {
    "typ": "entity-statement+jwt",
    "jwk": jwk,
    "kid": kid,
    "alg": "ES256",
}

# Encode the header and payload as Base64Url
encoded_header = base64url_encode(json.dumps(header).encode("utf-8"))
encoded_payload = base64url_encode(json.dumps(entity_statement).encode("utf-8"))

# Sign the JWT
signature = private_key.sign(
    f"{encoded_header}.{encoded_payload}".encode("utf-8"),
    ec.ECDSA(hashes.SHA256()),
)
encoded_signature = base64url_encode(signature)

# Assemble the JWT
signed_jwt = f"{encoded_header}.{encoded_payload}.{encoded_signature}"
print("Generated JWT:")
print(signed_jwt)

# Verify the JWT Signature
try:
    # Decode the signature
    public_key.verify(
        base64.urlsafe_b64decode(encoded_signature + "==="),
        f"{encoded_header}.{encoded_payload}".encode("utf-8"),
        ec.ECDSA(hashes.SHA256()),
    )
    print("Signature verification succeeded. The JWT is valid.")
except InvalidSignature:
    print("Signature verification failed. The JWT is invalid.")
