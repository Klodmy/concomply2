from werkzeug.security import generate_password_hash, check_password_hash

# hashing password
def hash_password(password:str) -> str:
    return generate_password_hash(password)

# checks if password matches stored hash value
def verify_password(password: str, hashed: str) -> bool:
    return check_password_hash(hashed, password)