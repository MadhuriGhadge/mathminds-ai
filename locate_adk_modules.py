
import pkgutil
import google.adk
import importlib

def list_submodules(package, prefix):
    print(f"package: {prefix}")
    for loader, module_name, is_pkg in pkgutil.walk_packages(package.__path__, prefix + "."):
        print(module_name)
        if is_pkg:
            try:
                module = importlib.import_module(module_name)
                # print(dir(module))
            except Exception as e:
                print(f"Failed to import {module_name}: {e}")

list_submodules(google.adk, "google.adk")
