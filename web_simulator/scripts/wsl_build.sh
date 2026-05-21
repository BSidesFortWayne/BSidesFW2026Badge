#!/bin/bash
set -euo pipefail

PROJECT_DIR="/mnt/c/Users/luke/BSidesFW2025Badge"
FREEZE_DIR="/home/luke/badge_freeze"
MP_DIR="/tmp/micropython"
EMSDK_DIR="/tmp/emsdk"
BUILD_OUT="$PROJECT_DIR/web_simulator/build"

echo "=== Preparing frozen modules ==="
rm -rf "$FREEZE_DIR"
mkdir -p "$FREEZE_DIR"

# Copy web shims
echo "  Copying web shims..."
cp "$PROJECT_DIR/web_simulator/py_shims/"*.py "$FREEZE_DIR/"

# Copy badge firmware
echo "  Copying badge firmware..."
for subdir in apps drivers lib ui services; do
    if [ -d "$PROJECT_DIR/src/$subdir" ]; then
        cp -r "$PROJECT_DIR/src/$subdir" "$FREEZE_DIR/"
    fi
done

for f in main.py boot.py controller.py bsp.py icontroller.py hardware_rev.py hardware_setup.py app_directory.py single_app_runner.py; do
    if [ -f "$PROJECT_DIR/src/$f" ]; then
        cp "$PROJECT_DIR/src/$f" "$FREEZE_DIR/"
    fi
done

# Remove conflicting modules that have web shim replacements at the top level
# drivers/gc9a01.py conflicts with the gc9a01.py shim (displays.py uses `import gc9a01`)
rm -f "$FREEZE_DIR/drivers/gc9a01.py"

echo "  Frozen module count: $(find "$FREEZE_DIR" -name '*.py' | wc -l)"

# Strip all @micropython.native/@micropython.viper decorators from frozen code
echo "  Stripping native/viper decorators..."
python3 "$PROJECT_DIR/web_simulator/scripts/patch_native_decorators.py" "$FREEZE_DIR"

# Patch microfont.py viper-specific ptr8/ptr16 types with pure-Python fallback
echo "  Patching microfont.py draw_ch_blit..."
python3 "$PROJECT_DIR/web_simulator/scripts/patch_microfont.py" "$FREEZE_DIR/lib/microfont.py"

# Activate Emscripten
echo "=== Activating Emscripten ==="
source "$EMSDK_DIR/emsdk_env.sh" 2>/dev/null
emcc --version | head -1

# Create manifest.py for MicroPython freeze
echo "=== Creating freeze manifest ==="
cat > /tmp/badge_manifest.py << 'MANIFEST_EOF'
import os, sys

# Include the default webassembly variant manifest which provides
# asyncio with JavaScript event loop integration
include("$(PORT_DIR)/variants/manifest.py")

freeze_dir = os.environ.get("BADGE_FREEZE_DIR", "/home/luke/badge_freeze")

# Freeze all top-level .py files (shims + firmware entry points)
for f in os.listdir(freeze_dir):
    if f.endswith('.py') and os.path.isfile(os.path.join(freeze_dir, f)):
        freeze(freeze_dir, f)

# Freeze subdirectories
for subdir in ['apps', 'drivers', 'lib', 'ui', 'services']:
    subdir_path = os.path.join(freeze_dir, subdir)
    if os.path.isdir(subdir_path):
        for root, dirs, files in os.walk(subdir_path):
            for f in files:
                if f.endswith('.py'):
                    rel = os.path.relpath(os.path.join(root, f), freeze_dir)
                    freeze(freeze_dir, rel)
MANIFEST_EOF

# Build MicroPython WASM
echo "=== Building MicroPython WASM port ==="
cd "$MP_DIR/ports/webassembly"
make submodules 2>&1 | tail -3
echo "  Running make..."
# Increase ASYNCIFY stack size for deep call chains (framebuffer apps)
if ! grep -q "ASYNCIFY_STACK_SIZE" "$MP_DIR/ports/webassembly/variants/standard/mpconfigvariant.mk"; then
    echo 'JSFLAGS += -s ASYNCIFY_STACK_SIZE=32768' >> "$MP_DIR/ports/webassembly/variants/standard/mpconfigvariant.mk"
fi
BADGE_FREEZE_DIR="$FREEZE_DIR" make FROZEN_MANIFEST=/tmp/badge_manifest.py CFLAGS_EXTRA="-Wno-unused-but-set-variable -Wno-unused-but-set-global" -j4 2>&1 | tail -20

echo "=== Copying build output ==="
mkdir -p "$BUILD_OUT"
cp "$MP_DIR/ports/webassembly/build-standard/micropython.mjs" "$BUILD_OUT/"
cp "$MP_DIR/ports/webassembly/build-standard/micropython.wasm" "$BUILD_OUT/"

# Patch micropython.mjs to prevent ASYNCIFY re-entrancy in proxy_call_python
echo "  Patching micropython.mjs for ASYNCIFY re-entrancy..."
python3 "$PROJECT_DIR/web_simulator/scripts/patch_mjs.py" "$BUILD_OUT/micropython.mjs"

echo "=== Packaging assets ==="
ASSETS_DIR="$BUILD_OUT/fs"
rm -rf "$ASSETS_DIR"
mkdir -p "$ASSETS_DIR"

for asset_dir in fonts songs img config apps; do
    if [ -d "$PROJECT_DIR/src/$asset_dir" ]; then
        cp -r "$PROJECT_DIR/src/$asset_dir" "$ASSETS_DIR/"
    fi
done

# Generate manifest.json
python3 -c "
import os, json
assets_dir = '$ASSETS_DIR'
files = []
for root, dirs, filenames in os.walk(assets_dir):
    for f in filenames:
        full = os.path.join(root, f)
        rel = os.path.relpath(full, assets_dir)
        files.append(rel.replace(os.sep, '/'))
print(json.dumps({'files': sorted(files)}, indent=2))
" > "$BUILD_OUT/manifest.json"

echo ""
echo "=== Build Complete ==="
ls -lh "$BUILD_OUT/micropython.wasm" "$BUILD_OUT/micropython.mjs"
echo "Asset files: $(cat "$BUILD_OUT/manifest.json" | python3 -c 'import sys,json; print(len(json.load(sys.stdin)["files"]))')"
