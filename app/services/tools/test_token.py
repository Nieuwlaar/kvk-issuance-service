import base64
import json
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, EllipticCurvePublicNumbers, ECDSA
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

def base64url_decode(data):
    """Decode a Base64Url encoded string."""
    padding = "=" * (4 - len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)

def validate_public_key(jwk):
    """Validate that the public key is correctly generated from JWK values."""
    try:
        # Extract x and y coordinates from the JWK
        x = int.from_bytes(base64url_decode(jwk["x"]), "big")
        y = int.from_bytes(base64url_decode(jwk["y"]), "big")
        
        # Create the public key
        curve = SECP256R1()
        public_numbers = EllipticCurvePublicNumbers(x, y, curve)
        public_key = public_numbers.public_key()
        
        # Export the public key in PEM format for debugging
        pem = public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        print("Derived Public Key (PEM):")
        print(pem.decode())
        
        return public_key
    except Exception as e:
        print(f"Public key validation failed: {e}")
        raise

def debug_jwt(jwt, jwk):
    """
    Debug a JWT by validating its signature against the provided JWK.
    
    Args:
        jwt (str): The JWT string to debug.
        jwk (dict): The JWK containing the public key.
    """
    try:
        # Split the JWT into its components
        header, payload, signature = jwt.split('.')
        
        # Decode Base64Url components
        decoded_header = json.loads(base64url_decode(header).decode('utf-8'))
        decoded_payload = json.loads(base64url_decode(payload).decode('utf-8'))
        decoded_signature = base64url_decode(signature)
        
        # Print decoded components
        print("Decoded Header:", json.dumps(decoded_header, indent=4))
        print("Decoded Payload:", json.dumps(decoded_payload, indent=4))
        print("Decoded Signature:", decoded_signature.hex())
        
        # Validate the public key
        public_key = validate_public_key(jwk)
        
        # Verify the signature
        public_key.verify(
            decoded_signature,
            f"{header}.{payload}".encode('utf-8'),
            ECDSA(SHA256())
        )
        
        print("Signature verification succeeded. The JWT is valid.")
    except InvalidSignature:
        print("Signature verification failed. The JWT is invalid.")
    except Exception as e:
        print(f"An error occurred during JWT validation: {e}")

def validate_jwk(jwk):
    """Validate that the JWK is well-formed and contains necessary fields."""
    required_fields = ["kty", "crv", "x", "y", "alg"]
    for field in required_fields:
        if field not in jwk:
            print(f"JWK validation failed: Missing field '{field}'")
            return False
    if jwk["kty"] != "EC" or jwk["crv"] != "P-256" or jwk["alg"] != "ES256":
        print("JWK validation failed: Incorrect key type, curve, or algorithm.")
        return False
    print("JWK validation passed.")
    return True

# Example inputs
jwt_token = "eyJ0eXAiOiAiZW50aXR5LXN0YXRlbWVudCtqd3QiLCAiandrIjogeyJrdHkiOiAiRUMiLCAiY3J2IjogIlAtMjU2IiwgIngiOiAidmladzM5SDUwOXhSdlpjTkh0R3c4aXhGZWV4YUY0TGExWlFMWlVXVFVVcyIsICJ5IjogInlkTjFvMExRQWRQVDF3di0wYjRZQk5zbVFwY1h6Zm1JS2lVaGh5NDJNWHciLCAia2lkIjogImF1dGhlbnRpY2F0aW9uLWtleSIsICJhbGciOiAiRVMyNTYifSwgImFsZyI6ICJFUzI1NiJ9.eyJpc3MiOiAiZGlkOndlYjp0ZXN0Lm1pbmlzdW9taS5maTphcGk6aXNzdWVyczprdmsiLCAic3ViIjogImRpZDp3ZWI6dGVzdC5taW5pc3VvbWkuZmk6YXBpOmlzc3VlcnM6a3ZrIiwgImF1dGhvcml0eV9oaW50cyI6IFsiaHR0cHM6Ly9ld2Mub2lkZi5maW5keS5maSJdLCAiandrcyI6IHsia2V5cyI6IFt7Imt0eSI6ICJFQyIsICJjcnYiOiAiUC0yNTYiLCAieCI6ICJ2aVp3MzlINTA5eFJ2WmNOSHRHdzhpeEZlZXhhRjRMYTFaUUxaVVdUVVVzIiwgInkiOiAieWROMW8wTFFBZFBUMXd2LTBiNFlCTnNtUXBjWHpmbUlLaVVoaHk0Mk1YdyIsICJraWQiOiAiYXV0aGVudGljYXRpb24ta2V5IiwgImFsZyI6ICJFUzI1NiJ9XX19.MEUCIQDXsWdD8K49TuRI5iGwwQwnL0PbUxwjv4S5yTKpVzh8awIgMb2ZCWGXOCj2L3wcyZaWrVuwU9466MTmc0Ss46797vQ"
jwk = {
    "kty": "EC",
    "crv": "P-256",
    "x": "viZw39H509xRvZcNHtGw8ixFeexaF4La1ZQLZUWTUUs",
    "y": "ydN1o0LQAdPT1wv-0b4YBNsmQpcXzfmIKiUhhy42MXw",
    "kid": "authentication-key",
    "alg": "ES256"
}

# Run the checks
if validate_jwk(jwk):
    debug_jwt(jwt_token, jwk)
