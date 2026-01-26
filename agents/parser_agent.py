import os
import glob
from typing import List
from langchain_openai import ChatOpenAI
from agents.schemas import FileList 
from state import AgentState

# Config
IGNORED_DIRS = {
    ".git", ".venv", "venv", "env", "node_modules", 
    "__pycache__", "dist", "build", ".idea", ".vscode"
}
MAX_FILES_LIMIT = 30

def get_all_files(root_dir: str) -> List[str]:
    found_files = []
    
    for root, dirs, files in os.walk(root_dir):
        # Filter directories to skip heavy folders
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        
        for file in files:
            # Check for supported extensions
            if file.endswith(('.py', '.md', '.env', '.json', '.txt')):
                found_files.append(os.path.join(root, file))
    
    return found_files

def parser_node(state: AgentState):
    print("\n--- 🔍 Step 1: Parser Agent ---")
    
    user_input = state["user_input"].strip()
    final_files = []

    # --- 1. HARD LOGIC (Priority) ---
    # Check if the input is a valid local path first
    if os.path.exists(user_input):
        if os.path.isdir(user_input):
            final_files.extend(get_all_files(user_input))
        elif os.path.isfile(user_input):
            final_files.append(user_input)
            
    # --- 2. LLM LOGIC (Fallback) ---
    # Only ask LLM if direct path resolution failed
    else:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        structured_llm = llm.with_structured_output(FileList)
        
        system_text = (
            "You are a file system assistant. The user will give you a path or a request.\n"
            "1. If it looks like a relative path (e.g. 'test_repo', 'src'), return it EXACTLY.\n"
            "2. Do NOT add '/path/to/' or make up folders."
        )
        
        response = structured_llm.invoke([
            ("system", system_text),
            ("user", user_input)
        ])
        
        cwd = os.getcwd()
        for path in response.paths:
            if os.path.exists(path):
                if os.path.isdir(path):
                    final_files.extend(get_all_files(path))
                elif os.path.isfile(path):
                    final_files.append(path)
            else:
                # Try relative check
                rel_path = os.path.join(cwd, path)
                if os.path.exists(rel_path):
                     if os.path.isdir(rel_path):
                        final_files.extend(get_all_files(rel_path))
                     elif os.path.isfile(rel_path):
                        final_files.append(rel_path)

    # --- 3. DEDUPLICATION & LIMITS ---
    final_files = list(set(final_files))
    
    # Safety Cap
    if len(final_files) > MAX_FILES_LIMIT:
        print(f"   ⚠️ Repo too large. Truncating to {MAX_FILES_LIMIT} files.")
        final_files = final_files[:MAX_FILES_LIMIT]
    
    print(f"   Targeting {len(final_files)} files.")
    return {"target_files": final_files}