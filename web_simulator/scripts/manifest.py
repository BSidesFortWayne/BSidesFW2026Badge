# MicroPython frozen manifest for BSides Badge Web Simulator
# Include the default WASM asyncio implementation first,
# then freeze all badge firmware + web shims.

import os

# Include the default webassembly variant manifest which provides
# asyncio with JavaScript event loop integration
include("$(PORT_DIR)/variants/manifest.py")

# The build script places all files to freeze in BADGE_FREEZE_DIR
freeze_dir = os.environ.get("BADGE_FREEZE_DIR", "/home/luke/badge_freeze")

if os.path.isdir(freeze_dir):
    # Freeze all top-level .py files (shims + firmware entry points)
    for f in sorted(os.listdir(freeze_dir)):
        full = os.path.join(freeze_dir, f)
        if f.endswith('.py') and os.path.isfile(full):
            freeze(freeze_dir, f)

    # Freeze subdirectories
    for subdir in ['apps', 'drivers', 'lib', 'ui', 'services', 'web']:
        subdir_path = os.path.join(freeze_dir, subdir)
        if os.path.isdir(subdir_path):
            for root, dirs, files in os.walk(subdir_path):
                for f in sorted(files):
                    if f.endswith('.py'):
                        rel = os.path.relpath(os.path.join(root, f), freeze_dir)
                        freeze(freeze_dir, rel)
