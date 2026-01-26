import os

REPO_NAME = "test_repov3_stress"

files = {
    # --- 1. THE BASICS (From v2) ---
    f"{REPO_NAME}/.env": "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE",
    f"{REPO_NAME}/src/clean.py": "print('Hello World')",
    f"{REPO_NAME}/docs/bad.md": "#NoSpace\nBad header.",

    # --- 2. 🕳️ EDGE CASE: EMPTY FILE ---
    # Tools often crash on empty input.
    f"{REPO_NAME}/src/empty.py": "",

    # --- 3. 🖼️ EDGE CASE: BINARY FILE (Fake Image) ---
    # If your Parser picks this up, your Processor might crash trying to read it.
    # We write bytes, not text.
    f"{REPO_NAME}/assets/logo.png": b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR',

    # --- 4. 📂 EDGE CASE: DEEP NESTING ---
    # Testing if os.walk recurses deeply enough.
    f"{REPO_NAME}/src/core/auth/v1/handlers/deep_logic.py": "def deep(): pass",

    # --- 5. 💀 EDGE CASE: MIXED THREAT ---
    # Contains a Secret AND Bad Python syntax.
    # Which tool does the Agent pick? (Should be Secrets or Python?)
    f"{REPO_NAME}/src/dangerous.py": """
def broken_code(
    print("Syntax Error here") 

# HARDCODED SECRET BELOW
api_key = "sk-1234567890abcdef1234567890abcdef"
"""
}

def create_repo():
    print(f"🚀 Creating '{REPO_NAME}' for Stress Testing...")
    
    if os.path.exists(REPO_NAME):
        print(f"⚠️  Warning: '{REPO_NAME}' already exists.")
    
    for file_path, content in files.items():
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Handle Binary vs Text writing
        mode = "wb" if isinstance(content, bytes) else "w"
        encoding = None if isinstance(content, bytes) else "utf-8"
        
        with open(file_path, mode, encoding=encoding) as f:
            f.write(content.strip() if isinstance(content, str) else content)
        
        print(f"   ✅ Created: {file_path}")

    print("\n🎉 Stress Test Repository Ready!")

if __name__ == "__main__":
    create_repo()