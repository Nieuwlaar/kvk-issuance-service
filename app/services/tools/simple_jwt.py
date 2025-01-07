import jwt
from jwt.algorithms import ECAlgorithm

# JWK Public Key
jwk = {
    "kty": "EC",
    "crv": "P-256",
    "x": "viZw39H509xRvZcNHtGw8ixFeeaF4La1ZQLZUWTTUs",
    "y": "ydN1o0LQAdPT1wv-0b4YBNsmQpcXzfmIKiUhh24M2MXw",
    "alg": "ES256"
}

# Convert JWK to a public key
key = ECAlgorithm.from_jwk(jwk)

# JWT
jwt_token = "eyJ0eXAiOiAiZW50aXR5LXN0YXRlbWVudCtqd3QiLCAiandrIjogeyJrdHkiOiAiRUMiLCAiY3J2IjogIlAtMjU2IiwgIngiOiAidmladzM5SDUwOXhSdlpjTkh0R3c4aXhGZWV4YUY0TGExWlFMWlVXVFVVcyIsICJ5IjogInlkTjFvMExRQWRQVDF3di0wYjRZQk5zbVFwY1h6Zm1JS2lVaGh5NDJNWHciLCAia2lkIjogImF1dGhlbnRpY2F0aW9uLWtleSIsICJhbGciOiAiRVMyNTYifSwgImtpZCI6ICJkaWQ6andrOmV5SnJkSGtpT2lKRlF5SXNJbU55ZGlJNklsQXRNalUySWl3aWVDSTZJblpwV25jek9VZzFNRGw0VW5aYVkwNUlkRWQzT0dsNFJtVmxlR0ZHTkV4aE1WcFJURnBWVjFSVlZYTWlMQ0o1SWpvaWVXUk9NVzh3VEZGQlpGQlVNWGQyTFRCaU5GbENUbk50VVhCaldIcG1iVWxMYVZWb2FIazBNazFZZHlJc0ltdHBaQ0k2SW1GMWRHaGxiblJwWTJGMGFXOXVMV3RsZVNJc0ltRnNaeUk2SWtWVE1qVTJJbjAiLCAiYWxnIjogIkVTMjU2In0.eyJpc3MiOiAiZGlkOndlYjp0ZXN0Lm1pbmlzdW9taS5maTphcGk6aXNzdWVyczprdmsiLCAic3ViIjogImRpZDp3ZWI6dGVzdC5taW5pc3VvbWkuZmk6YXBpOmlzc3VlcnM6a3ZrIiwgImF1dGhvcml0eV9oaW50cyI6IFsiaHR0cHM6Ly9ld2Mub2lkZi5maW5keS5maSJdLCAiandrcyI6IHsia2V5cyI6IFt7Imt0eSI6ICJFQyIsICJjcnYiOiAiUC0yNTYiLCAieCI6ICJ2aVp3MzlINTA5eFJ2WmNOSHRHdzhpeEZlZXhhRjRMYTFaUUxaVVdUVVVzIiwgInkiOiAieWROMW8wTFFBZFBUMXd2LTBiNFlCTnNtUXBjWHpmbUlLaVVoaHk0Mk1YdyIsICJraWQiOiAiYXV0aGVudGljYXRpb24ta2V5IiwgImFsZyI6ICJFUzI1NiJ9XX19.MEUCIQDtozT5b38G4MNo5EtCMDb-1mCL2xYkr2z0Zgx3jD08zAIgDqNpGkWb8ktJzJHMazBzud3KDl8kVkSOriNAYm9GXpQ"

# Decode and verify
try:
    decoded = jwt.decode(jwt_token, key, algorithms=["ES256"], options={"verify_aud": False})
    print("JWT is valid:", decoded)
except jwt.exceptions.InvalidTokenError as e:
    print("JWT validation failed:", e)
