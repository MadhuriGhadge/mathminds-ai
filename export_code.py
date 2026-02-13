import os

def collect_code(root_dir, output_file):
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for root, dirs, files in os.walk(root_dir):
            # Exclude directories
            dirs[:] = [d for d in dirs if d not in ['.venv', 'venv', '__pycache__', '.git', '.gemini', '.agent']]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    # Write Header
                    outfile.write(f"\n{'='*80}\n")
                    outfile.write(f"FILE: {file_path}\n")
                    outfile.write(f"{'='*80}\n\n")
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as infile:
                            outfile.write(infile.read())
                            outfile.write("\n")
                    except Exception as e:
                        outfile.write(f"Error reading file: {e}\n")

if __name__ == "__main__":
    # Run from project root ideally, or specify absolute path
    project_root = r"e:\madhuri\mathminds"
    output_path = os.path.join(project_root, "all_code.txt")
    print(f"Scanning {project_root}...")
    collect_code(project_root, output_path)
    print(f"Done. Saved to {output_path}")

