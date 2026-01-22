from werkzeug.security import generate_password_hash, check_password_hash
from pypdf import PdfReader

# hashing password
def hash_password(password:str) -> str:
    return generate_password_hash(password)

# checks if password matches stored hash value
def verify_password(password: str, hashed: str) -> bool:
    return check_password_hash(hashed, password)

def pdfs(pdf_file):
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text