"""Hot-reload support for the web simulator's in-browser editor.

The simulator's badge firmware is frozen into the WASM binary at build time,
so MicroPython's import system would always pick the frozen version of a
module even if filesystem overlays existed. This module bypasses the import
system by manually constructing a module object, executing the edited source
into its __dict__, and registering it in sys.modules (and as an attribute
on its parent package).

After swapping an app module, `reload_app` updates the AppDirectory's cached
AppMetadata and calls `Controller.switch_app` to tear down + re-enter the
running app, picking up the new constructor.
"""

import sys


def _materialise_module(module_path, source):
    """Create a brand-new (non-frozen) module on the filesystem and import it.

    MicroPython finds a submodule `pkg.leaf` only by looking in `pkg.__path__`,
    so we write `source` to `/<pkg>/leaf.py` and point the parent package's
    __path__ at that directory before importing. The fs copies of bundled apps
    are identical to the frozen ones, so redirecting __path__ is safe.
    """
    if "." in module_path:
        parent, leaf = module_path.rsplit(".", 1)
        base = "/" + parent.replace(".", "/")
    else:
        parent, leaf, base = "", module_path, ""

    # Ensure the parent directory exists (best-effort; usually already does).
    if base:
        try:
            import os
            os.mkdir(base)
        except OSError:
            pass

    with open((base + "/" if base else "/") + leaf + ".py", "w") as f:
        f.write(source)

    if parent:
        __import__(parent)
        sys.modules[parent].__path__ = base
    __import__(module_path)


def swap(module_path, source):
    """Replace `module_path` (e.g. 'apps.menu') with `source` (str).

    MicroPython doesn't expose a `types.ModuleType` constructor, so instead
    of synthesising a fresh module object we ensure the target module is
    imported (creates the real frozen-or-fs module), then re-`exec` the
    edited source into that module's `__dict__`. This replaces every
    top-level definition (classes, functions, constants) while keeping the
    same module object — so callers holding a reference to `apps.foo` see
    the new class definitions on next attribute lookup.

    Returns the (mutated) module object.
    """
    if module_path not in sys.modules:
        try:
            __import__(module_path)
        except ImportError:
            # Brand-new module: not frozen, never imported. MicroPython can't
            # synthesise a module object, and it resolves submodules only via
            # the parent package's __path__ (it does NOT scan sys.path), so we
            # materialise the source as a real file under the parent package's
            # filesystem dir and import it from there.
            _materialise_module(module_path, source)
    mod = sys.modules[module_path]

    # Mark the file path so tracebacks point at the overlay.
    overlay_file = "<overlay:%s>" % module_path

    # Clear out the existing namespace except for the dunder essentials
    # so removed top-level names don't linger.
    preserved = {"__name__", "__file__", "__path__"}
    for k in list(mod.__dict__.keys()):
        if k not in preserved:
            del mod.__dict__[k]
    mod.__dict__["__file__"] = overlay_file

    code = compile(source, overlay_file, "exec")
    exec(code, mod.__dict__)
    return mod


async def reload_app(controller, module_path, source):
    """Hot-swap an `apps.<name>` module and switch to it.

    Only valid for module_path values that start with 'apps.'. For other
    modules, use `swap` directly + a full page reload if controller state
    needs to reset.
    """
    swap(module_path, source)

    if not module_path.startswith("apps."):
        # Not an app — caller should also trigger a Full Reload to be safe.
        print("[hot_reload] swapped %s (not an app; consider Full Reload)" % module_path)
        return

    short = module_path.split(".", 1)[1]

    from app_directory import AppMetadata, ModuleMetadata

    new_apps = AppMetadata.from_module(short)
    if not new_apps:
        print("[hot_reload] no BaseApp subclasses found in %s" % module_path)
        return

    # Ensure the AppDirectory has a ModuleMetadata entry to attach apps to.
    mod_entry = controller.app_directory.modules.get(short)
    if mod_entry is None:
        mod_entry = ModuleMetadata(filename=short + ".py", checksum="overlay")
        controller.app_directory.modules[short] = mod_entry
    mod_entry.apps = new_apps

    # If the currently running app is the one we swapped, restart it.
    current = controller.current_view
    target_name = new_apps[0].friendly_name
    if current is not None and type(current).__module__ == module_path:
        await controller.switch_app(target_name)
    else:
        print("[hot_reload] swapped %s; switch to '%s' to see changes"
              % (module_path, target_name))
