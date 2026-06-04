#!/bin/bash
set -euo pipefail

# BSides FW 2025 Badge - Web Simulator Build Script
# Compiles MicroPython to WASM with frozen badge firmware

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEB_SIM_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$WEB_SIM_DIR")"
BUILD_DIR="$WEB_SIM_DIR/build"
DEPS_DIR="$WEB_SIM_DIR/.deps"

echo "=== BSides Badge Web Simulator Build ==="
echo "Project: $PROJECT_DIR"
echo "Output:  $BUILD_DIR"
echo ""

# Step 1: Install/verify Emscripten SDK
if [ ! -d "$DEPS_DIR/emsdk" ]; then
    echo "[1/6] Installing Emscripten SDK..."
    mkdir -p "$DEPS_DIR"
    git clone https://github.com/emscripten-core/emsdk.git "$DEPS_DIR/emsdk"
    cd "$DEPS_DIR/emsdk"
    ./emsdk install latest
    ./emsdk activate latest
else
    echo "[1/6] Emscripten SDK found"
fi
source "$DEPS_DIR/emsdk/emsdk_env.sh" 2>/dev/null || true

# Warm up emcc sanity cache serially. Avoids a Python 3.14 race in
# emscripten/tools/filelock.py where parallel emcc jobs unlink cache.lock
# concurrently and one of them blows up.
emcc --check >/dev/null 2>&1 || true

# Step 2: Clone/update MicroPython
if [ ! -d "$DEPS_DIR/micropython" ]; then
    echo "[2/6] Cloning MicroPython..."
    git clone https://github.com/micropython/micropython.git "$DEPS_DIR/micropython"
else
    echo "[2/6] MicroPython source found"
    cd "$DEPS_DIR/micropython"
    git pull --ff-only 2>/dev/null || true
fi
MP_DIR="$DEPS_DIR/micropython"

# Step 2b: Apply local MicroPython patches (idempotent)
WEBASM_MAIN="$MP_DIR/ports/webassembly/main.c"
if [ -f "$WEBASM_MAIN" ] && ! grep -q 'external_call_depth __attribute__((unused))' "$WEBASM_MAIN"; then
    echo "  Patching ports/webassembly/main.c for -Werror=unused-but-set-variable..."
    sed -i 's/^static size_t external_call_depth = 0;$/static size_t external_call_depth __attribute__((unused)) = 0;/' "$WEBASM_MAIN"
fi

# Step 3: Build mpy-cross
echo "[3/6] Building mpy-cross..."
cd "$MP_DIR"
make -C mpy-cross -j$(nproc 2>/dev/null || echo 4)

# Step 4: Prepare frozen modules
echo "[4/6] Preparing frozen modules..."
FREEZE_DIR="$BUILD_DIR/frozen"
rm -rf "$FREEZE_DIR"
mkdir -p "$FREEZE_DIR"

# Copy web shims (these override hardware modules)
cp "$WEB_SIM_DIR/py_shims/"*.py "$FREEZE_DIR/"

# Copy badge firmware source
for subdir in apps drivers lib ui services; do
    if [ -d "$PROJECT_DIR/src/$subdir" ]; then
        cp -r "$PROJECT_DIR/src/$subdir" "$FREEZE_DIR/"
    fi
done

# Copy top-level firmware files
for f in main.py boot.py controller.py bsp.py icontroller.py hardware_rev.py \
         hardware_setup.py app_directory.py single_app_runner.py; do
    if [ -f "$PROJECT_DIR/src/$f" ]; then
        cp "$PROJECT_DIR/src/$f" "$FREEZE_DIR/"
    fi
done

# Apply microfont viper fallback
if [ -f "$FREEZE_DIR/lib/microfont.py" ]; then
    echo "  Patching microfont.py for pure-Python fallback..."
    python3 "$SCRIPT_DIR/patch_microfont.py" "$FREEZE_DIR/lib/microfont.py"
fi

# Strip @micropython.native / @micropython.viper — unsupported on WASM port.
echo "  Stripping native/viper decorators from frozen sources..."
python3 "$SCRIPT_DIR/patch_native_decorators.py" "$FREEZE_DIR"

# Step 5: Build MicroPython WASM
echo "[5/6] Building MicroPython WASM port..."
cd "$MP_DIR/ports/webassembly"
make submodules
make clean
BADGE_FREEZE_DIR="$FREEZE_DIR" make \
    FROZEN_MANIFEST="$WEB_SIM_DIR/scripts/manifest.py" \
    -j$(nproc 2>/dev/null || echo 4)

# Step 6: Copy build artifacts
echo "[6/6] Copying build artifacts..."
mkdir -p "$BUILD_DIR"
MP_BUILD_OUT="$MP_DIR/ports/webassembly/build-standard"
if [ ! -f "$MP_BUILD_OUT/micropython.mjs" ]; then
    MP_BUILD_OUT="$MP_DIR/ports/webassembly/build"
fi
cp "$MP_BUILD_OUT/micropython.mjs" "$BUILD_DIR/"
cp "$MP_BUILD_OUT/micropython.wasm" "$BUILD_DIR/"

# Patch micropython.mjs to fix ASYNCIFY re-entrancy in proxy_call_python.
echo "  Patching micropython.mjs for async re-entrancy..."
python3 "$SCRIPT_DIR/patch_mjs.py" "$BUILD_DIR/micropython.mjs"

# Package non-Python assets (fonts, images, songs, configs)
echo "  Packaging firmware assets..."
ASSETS_DIR="$BUILD_DIR/fs"
rm -rf "$ASSETS_DIR"
mkdir -p "$ASSETS_DIR"

for asset_dir in fonts songs img config; do
    if [ -d "$PROJECT_DIR/src/$asset_dir" ]; then
        cp -r "$PROJECT_DIR/src/$asset_dir" "$ASSETS_DIR/"
    fi
done

# apps/ is enumerated at runtime by app_directory.py via os.listdir(), and
# each file is read for checksumming. The frozen copy isn't enough — the
# files must exist in MEMFS too.
if [ -d "$PROJECT_DIR/src/apps" ]; then
    cp -r "$PROJECT_DIR/src/apps" "$ASSETS_DIR/"
    # Same decorator strip as the freeze dir — the runtime parser also
    # can't handle @micropython.native / @micropython.viper on the WASM port.
    python3 "$SCRIPT_DIR/patch_native_decorators.py" "$ASSETS_DIR/apps" >/dev/null
fi

# Generate manifest.json for the web loader
python3 -c "
import os, json
files = []
for root, dirs, filenames in os.walk('$ASSETS_DIR'):
    for f in filenames:
        full = os.path.join(root, f)
        rel = os.path.relpath(full, '$ASSETS_DIR')
        files.append(rel)
print(json.dumps({'files': sorted(files)}, indent=2))
" > "$BUILD_DIR/manifest.json"

# Ship the src/ tree to the browser for the in-browser editor.
# These files are not loaded into MEMFS — they're fetched on demand
# by the editor (js/editor.js) so users can view/edit any source file.
echo "  Packaging src/ tree for in-browser editor..."
SRC_MIRROR="$BUILD_DIR/src"
rm -rf "$SRC_MIRROR"
mkdir -p "$SRC_MIRROR"
cp -r "$PROJECT_DIR/src/." "$SRC_MIRROR/"

# Generate src_index.json — list of every .py file (relative to src/)
python3 -c "
import os, json
files = []
for root, dirs, filenames in os.walk('$SRC_MIRROR'):
    for f in filenames:
        if f.endswith('.py'):
            full = os.path.join(root, f)
            rel = os.path.relpath(full, '$SRC_MIRROR').replace(os.sep, '/')
            files.append(rel)
print(json.dumps({'files': sorted(files)}, indent=2))
" > "$BUILD_DIR/src_index.json"

echo ""
echo "=== Build Complete ==="
echo "Output files:"
ls -lh "$BUILD_DIR/micropython.wasm" "$BUILD_DIR/micropython.mjs" 2>/dev/null || echo "  (WASM files)"
echo ""
echo "To serve locally:"
echo "  cd $WEB_SIM_DIR && python3 -m http.server 8080"
echo "  Open http://localhost:8080"
