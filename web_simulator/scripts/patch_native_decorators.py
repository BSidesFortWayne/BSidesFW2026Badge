"""Strip @micropython.native and @micropython.viper decorators from all .py files
in a directory tree. These decorators are not supported in the WASM port."""

import os
import sys
import re


def patch_file(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    original = content

    # Remove @micropython.native and @micropython.viper decorator lines
    content = re.sub(r'^\s*@micropython\.native\s*\n', '', content, flags=re.MULTILINE)
    content = re.sub(r'^\s*@micropython\.viper\s*\n', '', content, flags=re.MULTILINE)

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False


def patch_directory(directory):
    patched = []
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f.endswith('.py') or not '.' in f:
                filepath = os.path.join(root, f)
                if patch_file(filepath):
                    rel = os.path.relpath(filepath, directory)
                    patched.append(rel)

    if patched:
        print(f"  Stripped native/viper decorators from {len(patched)} files:")
        for p in patched:
            print(f"    {p}")
    else:
        print("  No native/viper decorators found")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <directory>")
        sys.exit(1)
    patch_directory(sys.argv[1])
