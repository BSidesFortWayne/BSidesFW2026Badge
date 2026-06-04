#!/usr/bin/env python3
"""
Quick Demo of Regression Test System

This script demonstrates the regression test capabilities by running
a simple automated test that:
1. Starts the simulator
2. Captures screenshots
3. Simulates button presses
4. Verifies the screenshot functionality

Usage:
    ./demo_regression_test.py
"""

import sys
import time
from pathlib import Path

# Add current directory to path to import regression_test
sys.path.insert(0, str(Path(__file__).parent))

from regression_test import SimulatorClient, RegressionTest


def main():
    print("="*60)
    print("Badge Simulator - Regression Test Demo")
    print("="*60)
    print()
    print("This demo will:")
    print("  1. Start the simulator")
    print("  2. Wait for initialization")
    print("  3. Capture initial screenshot")
    print("  4. Simulate button presses")
    print("  5. Capture state after button press")
    print("  6. Stop the simulator")
    print()
    print("Note: This is a quick test to verify the screenshot")
    print("      and button simulation functionality.")
    print()
    
    input("Press Enter to start demo...")
    
    # Create test instance
    test = RegressionTest(baseline_mode=True)
    
    try:
        # Step 1: Start simulator
        print("\n[1/6] Starting simulator...")
        if not test.start_simulator():
            print("✗ Failed to start simulator")
            return 1
        print("✓ Simulator running")
        
        # Step 2: Wait for init
        print("\n[2/6] Waiting for initialization (5s)...")
        time.sleep(5)
        print("✓ Simulator should be ready")
        
        # Step 3: First screenshot
        print("\n[3/6] Capturing initial screenshot...")
        success, path = test.capture_state('demo_initial', 'Initial simulator state')
        if success:
            print(f"✓ Screenshot saved: {path}")
        else:
            print(f"✗ Screenshot failed: {path}")
            return 1
        
        # Step 4: Button press
        print("\n[4/6] Simulating button press (DOWN button)...")
        try:
            response = test.client.send_command('button', 'press', {
                'button': 4,  # DOWN button
                'duration': 0.1
            })
            if response.get('status') == 'ok':
                print("✓ Button press simulated")
            else:
                print(f"⚠ Button press response: {response}")
        except Exception as e:
            print(f"⚠ Button press note: {e}")
            print("  (Button press may not affect UI if menu isn't active)")
        
        # Step 5: Wait and capture again
        print("\n[5/6] Waiting for UI update (1s)...")
        time.sleep(1)
        
        print("Capturing post-button screenshot...")
        success, path = test.capture_state('demo_after_button', 'State after button press')
        if success:
            print(f"✓ Screenshot saved: {path}")
        else:
            print(f"✗ Screenshot failed: {path}")
            return 1
        
        # Step 6: Done
        print("\n[6/6] Demo complete!")
        print()
        print("Screenshots saved to:")
        print(f"  {test.baseline_dir}")
        print()
        print("You can view the screenshots to verify:")
        print("  - Initial state was captured")
        print("  - Button press command was sent")
        print("  - Second screenshot was captured")
        print()
        print("Next steps:")
        print("  - Run: ./regression_test.py --create-baseline")
        print("  - Then: ./regression_test.py --compare")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
        return 1
    except Exception as e:
        print(f"\n✗ Demo error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        print("\nStopping simulator...")
        test.stop_simulator()


if __name__ == '__main__':
    sys.exit(main())
