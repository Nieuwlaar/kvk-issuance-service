from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1

# Load private key
with open("private_key.pem", "rb") as f:
    private_key = load_pem_private_key(f.read(), password=None)

# Derive public key
public_key = private_key.public_key()
public_numbers = public_key.public_numbers()

# Print x and y
print("x:", public_numbers.x)
print("y:", public_numbers.y)
import base64

# Decimal values of x and y
x_decimal = 86007360449054181777508313512093079175352479775542431878385924603731808309579
y_decimal = 91288499201734844821803938172679352567626361914771163595837695234884857377148

# Convert to bytes
x_bytes = x_decimal.to_bytes(32, byteorder='big')
y_bytes = y_decimal.to_bytes(32, byteorder='big')

# Encode to Base64Url
x_base64url = base64.urlsafe_b64encode(x_bytes).rstrip(b'=').decode('utf-8')
y_base64url = base64.urlsafe_b64encode(y_bytes).rstrip(b'=').decode('utf-8')

print("x (Base64Url):", x_base64url)
print("y (Base64Url):", y_base64url)
