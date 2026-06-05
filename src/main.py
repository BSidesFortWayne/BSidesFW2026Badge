import time
import gc
import os

from controller import Controller

gc.enable()
gc.collect()


async def main(displays):
    controller = Controller(displays, SIMULATOR)

    # Main thread, should be last to run
    asyncio.create_task(controller.run())

    while True:
        await asyncio.sleep(0.1)

if __name__ == "__main__":
    import asyncio
    
    # displays global should be created by boot.py (both hardware and simulator)
    # If it doesn't exist, create it as a fallback
    try:
        displays
    except NameError:
        print("Warning: displays not found from boot.py, creating fallback")
        import drivers.displays
        displays = drivers.displays.Displays()
    
    asyncio.run(main(displays))
