import os

def read_kalshi_credentials(pem_path):
    """
    Reads Kalshi email and API key from a .pem file in the format:
    email:your_email
    key:your_api_key
    """
    if not os.path.exists(pem_path):
        raise FileNotFoundError(f"Credential file not found: {pem_path}")
    
    with open(pem_path, "r") as f:
        lines = f.readlines()
    
    email = None
    api_key = None

    for line in lines:
        if line.startswith("email:"):
            email = line.split("email:")[1].strip()
        elif line.startswith("key:"):
            api_key = line.split("key:")[1].strip()
    
    if not email or not api_key:
        raise ValueError("Incomplete credentials in .pem file")

    return email, api_key