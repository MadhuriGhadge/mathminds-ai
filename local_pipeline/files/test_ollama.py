#!/usr/bin/env python3
"""
Diagnostic script to test Ollama connection and model availability.
Run this to troubleshoot MathMinds AI issues.
"""
import requests
import subprocess
import sys


def check_ollama_service():
    """Check if Ollama service is running."""
    print("1. Checking Ollama service...")
    try:
        resp = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            print("   ✓ Ollama service is running")
            return True, resp.json()
        else:
            print(f"   ✗ Ollama responded with status {resp.status_code}")
            return False, None
    except requests.exceptions.ConnectionError:
        print("   ✗ Cannot connect to Ollama (connection refused)")
        print("   → Is Ollama running? Try: ollama serve")
        return False, None
    except requests.exceptions.Timeout:
        print("   ✗ Connection to Ollama timed out")
        return False, None
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False, None


def check_models(data):
    """Check available models."""
    print("\n2. Checking available models...")
    if not data or "models" not in data:
        print("   ✗ No models found")
        return []
    
    models = data["models"]
    if not models:
        print("   ✗ No models installed")
        print("   → Install a model: ollama pull qwen2.5:3b-instruct-q4_K_M")
        return []
    
    print(f"   ✓ Found {len(models)} model(s):")
    model_names = []
    for model in models:
        name = model.get("name", "unknown")
        size = model.get("size", 0) / (1024**3)  # Convert to GB
        print(f"     - {name} ({size:.1f} GB)")
        model_names.append(name)
    
    return model_names


def check_required_model(model_names, required="qwen2.5:3b-instruct-q4_K_M"):
    """Check if required model is available."""
    print(f"\n3. Checking for required model: {required}")
    if required in model_names:
        print(f"   ✓ Model '{required}' is available")
        return True
    else:
        print(f"   ✗ Model '{required}' not found")
        print(f"   → Install it: ollama pull {required}")
        return False


def test_generation(model="qwen2.5:3b-instruct-q4_K_M"):
    """Test actual text generation."""
    print(f"\n4. Testing text generation with {model}...")
    try:
        payload = {
            "model": model,
            "prompt": "Say 'Hello World' and nothing else.",
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 50,
            }
        }
        
        print("   Sending request (this may take a few seconds)...")
        resp = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json=payload,
            timeout=60
        )
        
        if resp.status_code == 200:
            data = resp.json()
            response_text = data.get("response", "")
            print(f"   ✓ Generation successful!")
            print(f"   Response: {response_text[:100]}...")
            return True
        else:
            print(f"   ✗ Request failed with status {resp.status_code}")
            print(f"   Response: {resp.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print("   ✗ Request timed out (model may be loading)")
        print("   → Try running: ollama run " + model)
        return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False


def test_cli():
    """Test Ollama CLI."""
    print("\n5. Testing Ollama CLI...")
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"   ✓ Ollama CLI available: {version}")
            return True
        else:
            print("   ✗ Ollama CLI returned error")
            return False
    except FileNotFoundError:
        print("   ✗ Ollama CLI not found in PATH")
        return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False


def main():
    print("="*60)
    print("MathMinds AI - Ollama Diagnostic Tool")
    print("="*60)
    
    # Check service
    service_ok, data = check_ollama_service()
    if not service_ok:
        print("\n" + "="*60)
        print("DIAGNOSIS: Ollama service is not running")
        print("="*60)
        sys.exit(1)
    
    # Check models
    model_names = check_models(data)
    if not model_names:
        print("\n" + "="*60)
        print("DIAGNOSIS: No models installed")
        print("="*60)
        sys.exit(1)
    
    # Check required model
    required_model = "qwen2.5:3b-instruct-q4_K_M"
    model_ok = check_required_model(model_names, required_model)
    
    # Test generation if model exists
    if model_ok:
        gen_ok = test_generation(required_model)
    else:
        gen_ok = False
    
    # Test CLI
    cli_ok = test_cli()
    
    # Summary
    print("\n" + "="*60)
    print("DIAGNOSTIC SUMMARY")
    print("="*60)
    print(f"Ollama Service:    {'✓ OK' if service_ok else '✗ FAIL'}")
    print(f"Models Installed:  {'✓ OK' if model_names else '✗ FAIL'}")
    print(f"Required Model:    {'✓ OK' if model_ok else '✗ FAIL'}")
    print(f"Text Generation:   {'✓ OK' if gen_ok else '✗ FAIL'}")
    print(f"CLI Available:     {'✓ OK' if cli_ok else '✗ FAIL'}")
    print("="*60)
    
    if service_ok and model_ok and gen_ok:
        print("\n✓ All checks passed! MathMinds AI should work.")
        sys.exit(0)
    else:
        print("\n✗ Some checks failed. Fix the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()