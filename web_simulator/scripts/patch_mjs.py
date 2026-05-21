"""
Post-build patch for micropython.mjs to prevent ASYNCIFY re-entrancy crashes.

The MicroPython WASM port's proxy_call_python function uses ccall without
the {async: true} option. When Python code called from JS does any async
operation (asyncio.sleep_ms, js.* proxy calls), ASYNCIFY unwinds the C stack
and ccall asserts because it wasn't told async was expected.

Fix: Replace the entire proxy_call_python function with an async-aware
version that passes {async: true} to ccall and properly handles the
Promise return path.
"""

import sys
import re


def patch(mjs_path):
    with open(mjs_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if already patched
    if 'ASYNC_PATCHED' in content:
        print(f"  Already patched: {mjs_path}")
        return

    # Find and replace the entire proxy_call_python function.
    # Match from "function proxy_call_python" to the closing brace before
    # the next top-level function (proxy_convert_js_to_mp_obj_jsside_helper).
    pattern = r'function proxy_call_python\(target, argumentsList\) \{.*?\n\}'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        # Try matching the wrapper version from previous patch
        pattern = r'function _original_proxy_call_python\(target, argumentsList\) \{.*?\n\}'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            # Remove the old wrapper too
            old_wrapper_pattern = r'// --- PATCH:.*?// --- END PATCH ---\n+'
            content = re.sub(old_wrapper_pattern, '', content, flags=re.DOTALL)
            # Re-search after cleanup
            pattern = r'function _original_proxy_call_python\(target, argumentsList\) \{.*?\n\}'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                # Rename back
                content = content.replace('_original_proxy_call_python', 'proxy_call_python')
                match = re.search(r'function proxy_call_python\(target, argumentsList\) \{.*?\n\}', content, re.DOTALL)

    if not match:
        print(f"  ERROR: Could not find proxy_call_python in {mjs_path}")
        sys.exit(1)

    replacement = r'''function proxy_call_python(target, argumentsList) { // ASYNC_PATCHED
    // Strip trailing "undefined" arguments.
    while (
        argumentsList.length > 0 &&
        argumentsList[argumentsList.length - 1] === undefined
    ) {
        argumentsList.pop();
    }

    let args = 0;
    if (argumentsList.length > 0) {
        args = Module._malloc(argumentsList.length * 3 * 4);
        for (const i in argumentsList) {
            proxy_convert_js_to_mp_obj_jsside(
                argumentsList[i],
                args + i * 3 * 4,
            );
        }
    }
    const value = Module._malloc(3 * 4);
    const result = Module.ccall(
        "proxy_c_to_js_call",
        "null",
        ["number", "number", "number", "pointer"],
        [target, argumentsList.length, args, value],
        { async: true },
    );

    function finish() {
        if (argumentsList.length > 0) {
            Module._free(args);
        }
        const ret = proxy_convert_mp_to_js_obj_jsside_with_free(value);
        if (ret instanceof PyProxyThenable) {
            return Promise.resolve(ret);
        }
        return ret;
    }

    // ccall with {async:true} returns a Promise when ASYNCIFY kicks in
    if (result && typeof result.then === 'function') {
        return result.then(() => finish());
    }
    return finish();
}'''

    content = content[:match.start()] + replacement + content[match.end():]

    with open(mjs_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"  Patched proxy_call_python with {{async: true}} ccall")


if __name__ == '__main__':
    patch(sys.argv[1])
