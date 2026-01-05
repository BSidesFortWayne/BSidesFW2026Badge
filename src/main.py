import time
import gc
import os

from controller import Controller

gc.enable()
gc.collect()


async def main(displays):
    controller = Controller(displays)

    # Main thread, should be last to run
    asyncio.create_task(controller.run())

    while True:
        await asyncio.sleep(0.1)

if __name__ == "__main__":
    import asyncio
    
    # Check if running in simulator or on actual hardware
    # In simulator, boot.py doesn't run automatically, so we need to import displays here
    try:
        displays
    except NameError:
        import drivers.displays
        displays = drivers.displays.Displays()
    # if 'getenv' not in dir(os):
    #     os.getenv = lambda x: None

    # if os.getenv('BADGE_SIMULATOR'):
    #     # Simulator mode - create displays here since boot.py doesn't auto-run
    #     import drivers.displays
    #     displays = drivers.displays.Displays()
    # else:
    #     # Real hardware - displays should be created by boot.py
    #     # If not, import it
    #     try:
    #         displays
    #     except NameError:
    #         import drivers.displays
    #         displays = drivers.displays.Displays()
    
    asyncio.run(main(displays))
