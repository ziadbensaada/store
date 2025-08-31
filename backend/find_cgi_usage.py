import os
import sys

def find_cgi_usage(directory):
    """Search for Python files that import or use the cgi module."""
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if 'import cgi' in content or 'from cgi ' in content:
                            print(f"Found cgi import in: {filepath}")
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")

if __name__ == "__main__":
    directory = os.path.dirname(os.path.abspath(__file__))
    print(f"Searching for cgi module usage in: {directory}")
    find_cgi_usage(directory)
