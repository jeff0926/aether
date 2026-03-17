import argparse
import os
import shutil
import json
import hashlib
from datetime import datetime
from pathlib import Path

# Try to import optional AI libraries
try:
    from google import genai
    from dotenv import load_dotenv
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

def get_file_hash(filepath):
    """Returns the SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def clean_text(text):
    """Basic local cleaning to reduce tokens before sending to LLM."""
    lines = text.splitlines()
    cleaned = [line.strip() for line in lines if line.strip()]
    return "\n".join(cleaned)

def read_and_triage(input_dir):
    """Reads all files in the input directory and prepares them for the LLM."""
    corpus = []
    supported_extensions = {'.md', '.txt', '.json', '.jsonld'}
    
    print(f"[*] Reading and cleaning files from {input_dir}...")
    
    for root, dirs, files in os.walk(input_dir):
        # Skip archive directories if they exist inside input
        if '_arch' in root:
            continue
            
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix.lower() in supported_extensions:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Simple local optimization: skip massive raw JSONs if not needed, 
                        # or just take a snippet. For now, we take all but clean it.
                        cleaned_content = clean_text(content)
                        corpus.append(f"--- FILE: {file_path.relative_to(input_dir)} ---\n{cleaned_content}\n")
                except Exception as e:
                    print(f"[!] Could not read {file_path}: {e}")
    
    return "\n".join(corpus)

def call_gemini(prompt, api_key):
    """Calls Gemini API to process the corpus."""
    if not HAS_LIBS:
        return "Error: google-genai or python-dotenv not installed.", "{}"

    # Use the new Google GenAI SDK
    client = genai.Client(api_key=api_key)
    
    print("[*] Dispatching to Gemini (2.5 Flash)...")
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    return response.text

def create_aether_package(project_name, output_dir, corpus, api_key):
    """Generates the 5 foundational files using LLM synthesis."""
    print(f"[*] Synthesizing Aether Package for: {project_name}")
    os.makedirs(output_dir, exist_ok=True)
    
    # Prompt for synthesis
    prompt = f"""
    You are the Aether Harvester Agent. I will provide you with a corpus of files from a project directory.
    Your task is to distill this information into two specific outputs.

    OUTPUT 1: A comprehensive AETHER_KNOWLEDGE_BASE.md. 
    It must include:
    - Project Goal and Vision
    - Key Architectural Decisions (look for 'daily' and 'session-states' logs)
    - Current Status and Progress
    - Deferred Topics or Blockers (look for 'Deferred' files)
    - List of defined Agent Roles (look for JSON files in 'roles' or 'company-organization')

    OUTPUT 2: A valid JSON-LD Knowledge Graph (AETHER_KNOWLEDGE_KG.jsonld) that represents the project, its entities, and their relationships.

    FORMATTING:
    Provide your response as follows:
    ---KB_START---
    [Markdown Content]
    ---KB_END---
    ---KG_START---
    [JSON-LD Content]
    ---KG_END---

    CORPUS:
    {corpus}
    """

    synthesis = call_gemini(prompt, api_key)
    
    # Simple extraction logic from LLM response
    kb_content = ""
    kg_content = "{}"
    
    if "---KB_START---" in synthesis and "---KB_END---" in synthesis:
        kb_content = synthesis.split("---KB_START---")[1].split("---KB_END---")[0].strip()
    
    if "---KG_START---" in synthesis and "---KG_END---" in synthesis:
        kg_content = synthesis.split("---KG_START---")[1].split("---KG_END---")[0].strip()

    # CRITICAL FIX: Ensure utf-8 encoding is used on Windows when writing files containing emojis or arrows.
    # 1. Manifest
    with open(os.path.join(output_dir, f"{project_name}_Agent_manifest.json"), 'w', encoding='utf-8') as f:
        json.dump({"name": project_name, "type": "ProjectAgent", "generated_at": str(datetime.now())}, f, indent=4)
        
    # 2. Definition
    with open(os.path.join(output_dir, f"{project_name}_Agent_definition.json"), 'w', encoding='utf-8') as f:
        json.dump({"description": f"Core intelligence for {project_name}", "capabilities": ["autonomous_research", "context_distillation"]}, f, indent=4)
        
    # 3. Persona
    with open(os.path.join(output_dir, f"{project_name}_Agent_persona.json"), 'w', encoding='utf-8') as f:
        json.dump({"role": "Project Historian", "tone": "Concise and Architecturally focused"}, f, indent=4)
        
    # 4. Knowledge Base
    with open(os.path.join(output_dir, "AETHER_KNOWLEDGE_BASE.md"), 'w', encoding='utf-8') as f:
        f.write(kb_content if kb_content else f"# {project_name}\nKnowledge Base synthesis failed.\n\nRaw LLM Output:\n{synthesis}")
        
    # 5. Knowledge Graph
    with open(os.path.join(output_dir, "AETHER_KNOWLEDGE_KG.jsonld"), 'w', encoding='utf-8') as f:
        try:
            # Validate JSON
            json_obj = json.loads(kg_content)
            json.dump(json_obj, f, indent=4)
        except:
            f.write(kg_content if kg_content else "{}")
        
    print("[+] Aether Package generation complete.")

def archive_directory(input_dir, archive_dir):
    """Zips the processed directory."""
    if not os.path.exists(input_dir): return
    os.makedirs(archive_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    archive_name = os.path.join(archive_dir, f"archive_{timestamp}")
    shutil.make_archive(archive_name, 'zip', input_dir)
    print(f"[+] Archive created: {archive_name}.zip")

def main():
    parser = argparse.ArgumentParser(description="Aether Harvester")
    parser.add_argument("--input", default="IGNORE", help="Path to input")
    parser.add_argument("--output", default=".", help="Path to output")
    parser.add_argument("--archive", default="_arch", help="Path to archive")
    parser.add_argument("--name", default="Aether_Project", help="Project name")
    parser.add_argument("--env", default=".env", help="Path to .env file")
    
    args = parser.parse_args()

    # Load environment variables
    if HAS_LIBS:
        load_dotenv(args.env)
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[!] GEMINI_API_KEY not found in environment or .env file.")
        return

    print(f"=== Starting Aether Harvester: {args.name} ===")
    
    # 1. Triage & Clean (Local, 0 tokens)
    corpus = read_and_triage(args.input)
    
    # 2. Synthesize & Generate 5-File Package (Single API Call, Efficient)
    create_aether_package(args.name, args.output, corpus, api_key)
    
    # 3. Archive
    archive_directory(args.input, args.archive)
    
    print("=== Harvester Run Complete ===")

if __name__ == "__main__":
    main()