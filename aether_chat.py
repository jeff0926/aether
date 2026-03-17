import os
import sys
from pathlib import Path
from aether import Capsule
from llm import make_llm_fn

def chat():
    # Load the Aether_Alpha capsule
    if len(sys.argv) > 1:
        capsule_path = Path(sys.argv[1])
    else:
        # Try default locations
        capsule_path = Path("Aether_Alpha")
        if not capsule_path.exists():
            # Search in examples
            examples = Path("examples")
            if examples.exists():
                for folder in examples.iterdir():
                    if folder.is_dir() and "Aether_Alpha" in folder.name:
                        capsule_path = folder
                        break
    
    if not capsule_path.exists():
        print(f"Error: Capsule path {capsule_path} does not exist.")
        print("Usage: python aether_chat.py <capsule_path>")
        return

    # Initialize LLM function (prefer Anthropic, fallback to stub if no key)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    provider = "anthropic" if api_key else "stub"
    llm_fn = make_llm_fn(provider=provider)

    try:
        capsule = Capsule(capsule_path, llm_fn=llm_fn)
    except Exception as e:
        print(f"Error loading capsule: {e}")
        return

    print(f"--- Aether Chat: {capsule.name} (v{capsule.version}) ---")
    print(f"Role: {capsule.files['persona'].get('role', 'Unknown')}")
    print("Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            query = input("You: ").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit"]:
                break

            print("\nAether is thinking...", end="\r")
            ctx = capsule.run(query)
            
            response = ctx.get("generated", "[No response]")
            review = ctx.get("review", {})
            aec_score = review.get("aec", {}).get("score", 0.0)
            passed = review.get("passed", False)
            
            print(f"Aether: {response}")
            print(f"[AEC Score: {aec_score:.2f} | {'PASSED' if passed else 'FAILED'}]")
            
            if review.get("self_corrected"):
                print("[Note: Response was self-corrected via AEC retry]")
            if review.get("ghost"):
                print("[Note: Response is in GHOST state - unverifiable]")
            
            print("-" * 40)

        except KeyboardInterrupt:
            break
        except EOFError:
            break
        except Exception as e:
            print(f"\nError: {e}")

    print("\nGoodbye!")

if __name__ == "__main__":
    chat()
