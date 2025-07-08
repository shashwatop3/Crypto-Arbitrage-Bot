import requests
import json
from urllib.parse import urlparse, urlencode
import time
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import config

def generate_signature(api_secret: str, timestamp: str, method: str, path: str, params: dict = None, body: str = "") -> str:
    """Generate Ed25519 signature as per CoinSwitch API docs"""
    try:
        # Build the string to sign
        if method.upper() == 'GET' and params:
            query = urlencode(params)
            full_path = path + ('?' if '?' not in path else '&') + query
            # The message to sign should not include the base URL
            message_str = method.upper() + full_path + timestamp
        else:
            message_str = method.upper() + path + timestamp + body

        # Sign using Ed25519
        secret_key_bytes = bytes.fromhex(api_secret)
        private_key = Ed25519PrivateKey.from_private_bytes(secret_key_bytes)
        signature_bytes = private_key.sign(message_str.encode('utf-8'))
        return signature_bytes.hex()
    except Exception as e:
        print(f"Error generating signature: {e}")
        return "invalid_signature"

params = {
    "exchange": "coinswitchx", # As per API docs, use 'coinswitchx' for spot
}
payload = {}
endpoint = "/trade/api/v2/coins"
method = "GET"
timestamp = str(int(time.time() * 1000))

# Construct the full URL for the request
url = config.BASE_URL + endpoint

# Generate the signature
signature = generate_signature(config.API_SECRET, timestamp, method, endpoint, params=params)

headers = {
  'Content-Type': 'application/json',
  'X-AUTH-SIGNATURE': signature,
  'X-AUTH-APIKEY': config.API_KEY,
  'X-AUTH-EPOCH': timestamp
}

# Make the request with params in the 'params' argument of requests
response = requests.request(method, url, headers=headers, params=params, json=payload)

print(response.status_code)
print(response.text)