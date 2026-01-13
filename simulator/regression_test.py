#!/usr/bin/env python3
"""
AI-Driven Regression Test for Badge Simulator

This script automates visual regression testing by:
1. Starting the simulator
2. Simulating button presses to navigate the UI
3. Capturing screenshots at key states
4. Comparing screenshots to baselines (optional)
5. Generating a test report

Usage:
    # Run basic test suite
    ./regression_test.py
    
    # Run with baseline creation mode
    ./regression_test.py --create-baseline
    
    # Run with visual comparison
    ./regression_test.py --compare
    
    # Run specific test sequence
    ./regression_test.py --test menu_navigation
    
    # Custom simulator config
    ./regression_test.py --config my_config.json
"""

import socket
import json
import argparse
import time
import sys
import os
import subprocess
import signal
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple


class SimulatorClient:
    """Client for communicating with the badge simulator"""
    
    def __init__(self, host='127.0.0.1', port=4455, timeout=15.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = None
        
    def connect(self, max_retries=10, retry_delay=1.0):
        """Connect to simulator with retries"""
        for attempt in range(max_retries):
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(self.timeout)
                self.sock.connect((self.host, self.port))
                return True
            except (ConnectionRefusedError, socket.timeout):
                if attempt < max_retries - 1:
                    print(f"  Connection attempt {attempt + 1}/{max_retries} failed, retrying...")
                    time.sleep(retry_delay)
                else:
                    print(f"  Failed to connect after {max_retries} attempts")
                    return False
        return False
    
    def disconnect(self):
        """Close connection to simulator"""
        if self.sock:
            self.sock.close()
            self.sock = None
    
    def send_command(self, module: str, command: str, parameters: dict = None) -> dict:
        """Send command to simulator via JSON protocol"""
        if not self.sock:
            if not self.connect():
                raise ConnectionError("Not connected to simulator")
        
        cmd = {
            'module': module,
            'command': command,
            'parameters': parameters or {}
        }
        
        try:
            self.sock.sendall(json.dumps(cmd).encode('utf-8'))
            
            # Receive response
            response_data = b''
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                response_data += chunk
                try:
                    response = json.loads(response_data.decode('utf-8'))
                    return response
                except json.JSONDecodeError:
                    continue
        except socket.timeout:
            raise TimeoutError("Command timeout")
        finally:
            # Reconnect for next command (JSON protocol is one-shot)
            self.disconnect()
    
    def take_screenshot(self, filepath: str | None = None) -> str:
        """Capture screenshot from simulator"""
        response = self.send_command('screenshot', 'take', {'filepath': filepath} if filepath else {})
        
        if response.get('status') == 'ok' and 'resp' in response:
            return response['resp']
        else:
            raise RuntimeError(f"Screenshot failed: {response}")
    
    def press_button(self, button: int, duration: float = 0.1):
        """Simulate button press via JSON protocol
        
        Args:
            button: Button index (0-7)
            duration: How long to hold button (seconds)
        """
        try:
            response = self.send_command('button', 'press', {
                'button': button,
                'duration': duration
            })
            
            if response.get('status') == 'ok':
                # Wait for the button press to take effect
                time.sleep(duration + 0.1)
                return True
            else:
                print(f"    ✗ Button press failed: {response}")
                return False
        except Exception as e:
            print(f"    ✗ Button press error: {e}")
            return False


class RegressionTest:
    """Main regression test orchestrator"""
    
    def __init__(self, config_path: str = 'config.json', 
                 baseline_mode: bool = False,
                 compare_mode: bool = False):
        self.config_path = config_path
        self.baseline_mode = baseline_mode
        self.compare_mode = compare_mode
        
        # Test directories
        self.test_dir = Path('regression_tests')
        self.baseline_dir = self.test_dir / 'baseline'
        self.current_dir = self.test_dir / 'current'
        self.diff_dir = self.test_dir / 'diffs'
        
        # Create directories
        for d in [self.baseline_dir, self.current_dir, self.diff_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        self.client = SimulatorClient()
        self.simulator_process = None
        self.test_results = []
        
    def start_simulator(self) -> bool:
        """Start the simulator process"""
        print("Starting simulator...")
        
        try:
            # Start simulator in background with uv run
            self.simulator_process = subprocess.Popen(
                ['uv', 'run', 'python3', 'simulator.py', '-c', self.config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            
            # Wait for simulator to be ready
            print("Waiting for simulator to initialize...")
            time.sleep(5)  # Give it time to start up
            
            # Try to connect
            if self.client.connect(max_retries=15, retry_delay=1.0):
                print("✓ Simulator started and ready")
                return True
            else:
                print("✗ Simulator failed to start")
                return False
                
        except Exception as e:
            print(f"✗ Failed to start simulator: {e}")
            return False
    
    def stop_simulator(self):
        """Stop the simulator process"""
        if self.simulator_process:
            print("\nStopping simulator...")
            
            # Try graceful shutdown first
            try:
                if hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(self.simulator_process.pid), signal.SIGTERM)
                else:
                    self.simulator_process.terminate()
                
                # Wait for process to exit
                try:
                    self.simulator_process.wait(timeout=5)
                    print("✓ Simulator stopped gracefully")
                except subprocess.TimeoutExpired:
                    print("  Forcing simulator shutdown...")
                    if hasattr(os, 'killpg'):
                        os.killpg(os.getpgid(self.simulator_process.pid), signal.SIGKILL)
                    else:
                        self.simulator_process.kill()
                    self.simulator_process.wait()
                    print("✓ Simulator stopped (forced)")
            except Exception as e:
                print(f"  Warning: Error stopping simulator: {e}")
    
    def capture_state(self, name: str, description: str = "") -> Tuple[bool, str]:
        """Capture current simulator state as screenshot"""
        print(f"  Capturing: {name}")
        if description:
            print(f"    {description}")
        
        try:
            # Determine output directory
            output_dir = self.baseline_dir if self.baseline_mode else self.current_dir
            filepath = output_dir / f"{name}.png"
            
            # Take screenshot
            saved_path = self.client.take_screenshot(str(filepath))
            
            return True, saved_path
        except Exception as e:
            print(f"    ✗ Failed to capture: {e}")
            return False, str(e)
    
    def wait_for_state(self, seconds: float, description: str = ""):
        """Wait for UI to settle into a state"""
        if description:
            print(f"  Waiting: {description}")
        time.sleep(seconds)
    
    def run_test_sequence(self, sequence_name: str, steps: List[Dict[str, Any]]) -> bool:
        """Run a test sequence with multiple steps"""
        print(f"\n{'='*60}")
        print(f"Test Sequence: {sequence_name}")
        print(f"{'='*60}")
        
        all_passed = True
        
        for i, step in enumerate(steps, 1):
            print(f"\nStep {i}/{len(steps)}: {step.get('name', 'Unnamed')}")
            
            step_type = step.get('type')
            
            if step_type == 'wait':
                self.wait_for_state(step['duration'], step.get('description', ''))
                
            elif step_type == 'capture':
                success, result = self.capture_state(
                    step['name'],
                    step.get('description', '')
                )
                self.test_results.append({
                    'sequence': sequence_name,
                    'step': i,
                    'name': step['name'],
                    'success': success,
                    'result': result
                })
                if not success:
                    all_passed = False
                    
            elif step_type == 'button':
                button = step['button']
                duration = step.get('duration', 0.1)
                desc = step.get('description', f'Button {button}')
                print(f"    {desc}")
                if not self.client.press_button(button, duration):
                    all_passed = False
                
            else:
                print(f"    ✗ Unknown step type: {step_type}")
                all_passed = False
        
        return all_passed
    
    def compare_screenshots(self) -> Dict[str, Any]:
        """Compare current screenshots to baseline"""
        if not self.compare_mode:
            return {}
        
        print("\n" + "="*60)
        print("Visual Comparison")
        print("="*60)
        
        try:
            from PIL import Image, ImageChops, ImageStat
        except ImportError:
            print("✗ PIL not available, skipping visual comparison")
            print("  Install with: pip install Pillow")
            return {}
        
        comparison_results = {}
        
        # Find all baseline screenshots
        baseline_files = list(self.baseline_dir.glob("*.png"))
        
        if not baseline_files:
            print("✗ No baseline screenshots found")
            print(f"  Run with --create-baseline first")
            return {}
        
        print(f"\nComparing {len(baseline_files)} screenshots...")
        
        for baseline_path in baseline_files:
            name = baseline_path.stem
            current_path = self.current_dir / baseline_path.name
            
            if not current_path.exists():
                print(f"  ✗ {name}: Missing current screenshot")
                comparison_results[name] = {'status': 'missing', 'diff': None}
                continue
            
            try:
                # Load images
                baseline_img = Image.open(baseline_path)
                current_img = Image.open(current_path)
                
                # Ensure same size
                if baseline_img.size != current_img.size:
                    print(f"  ✗ {name}: Size mismatch")
                    comparison_results[name] = {'status': 'size_mismatch', 'diff': None}
                    continue
                
                # Calculate difference
                diff = ImageChops.difference(baseline_img, current_img)
                
                # Calculate RMS difference
                stat = ImageStat.Stat(diff)
                rms = sum(stat.rms) / len(stat.rms)  # Average RMS across channels
                
                # Save diff image if significant
                if rms > 1.0:  # Threshold for "different"
                    diff_path = self.diff_dir / f"{name}_diff.png"
                    
                    # Enhance diff for visibility
                    diff_enhanced = diff.point(lambda p: p * 10)
                    diff_enhanced.save(diff_path)
                    
                    print(f"  ⚠ {name}: Visual difference detected (RMS: {rms:.2f})")
                    print(f"    Diff saved to: {diff_path}")
                    comparison_results[name] = {'status': 'different', 'rms': rms, 'diff': str(diff_path)}
                else:
                    print(f"  ✓ {name}: Match (RMS: {rms:.2f})")
                    comparison_results[name] = {'status': 'match', 'rms': rms, 'diff': None}
                    
            except Exception as e:
                print(f"  ✗ {name}: Comparison error: {e}")
                comparison_results[name] = {'status': 'error', 'error': str(e), 'diff': None}
        
        return comparison_results
    
    def generate_report(self, comparison_results: Dict[str, Any]):
        """Generate test report"""
        print("\n" + "="*60)
        print("Test Report")
        print("="*60)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = self.test_dir / f"report_{timestamp}.json"
        
        report = {
            'timestamp': timestamp,
            'mode': 'baseline' if self.baseline_mode else 'test',
            'config': self.config_path,
            'test_results': self.test_results,
            'comparison_results': comparison_results,
            'summary': {
                'total_captures': len(self.test_results),
                'successful_captures': sum(1 for r in self.test_results if r['success']),
                'failed_captures': sum(1 for r in self.test_results if not r['success']),
            }
        }
        
        if comparison_results:
            report['summary']['total_comparisons'] = len(comparison_results)
            report['summary']['matches'] = sum(1 for r in comparison_results.values() if r.get('status') == 'match')
            report['summary']['differences'] = sum(1 for r in comparison_results.values() if r.get('status') == 'different')
            report['summary']['errors'] = sum(1 for r in comparison_results.values() if r.get('status') in ['error', 'missing', 'size_mismatch'])
        
        # Save report
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        print(f"\nCapture Summary:")
        print(f"  Total: {report['summary']['total_captures']}")
        print(f"  Successful: {report['summary']['successful_captures']}")
        print(f"  Failed: {report['summary']['failed_captures']}")
        
        if comparison_results:
            print(f"\nComparison Summary:")
            print(f"  Total: {report['summary']['total_comparisons']}")
            print(f"  Matches: {report['summary']['matches']}")
            print(f"  Differences: {report['summary']['differences']}")
            print(f"  Errors: {report['summary']['errors']}")
        
        print(f"\nReport saved to: {report_path}")
        
        # Return success status
        if self.baseline_mode:
            return report['summary']['failed_captures'] == 0
        else:
            return (report['summary']['failed_captures'] == 0 and
                   (not comparison_results or report['summary']['differences'] == 0))


def define_test_sequences() -> Dict[str, List[Dict[str, Any]]]:
    """Define test sequences for the badge UI
    
    Button mapping (simulator keyboard keys):
    - 0: Boot/Reset (SW5)
    - 1: SW1 (button 1)
    - 2: SW2 (button 2)  
    - 3: SW3 (button 3)
    - 4: SW4 / DOWN button
    - 5: SW7 / UP button
    - 6: SW8 / SELECT button
    - 7: SW9 (game button 3)
    
    Note: The simulator's button_states array maps to hardware buttons.
    For menu navigation, we typically use:
    - Button 4: DOWN
    - Button 5: UP
    - Button 6: SELECT
    """
    
    sequences = {
        'startup': [
            {
                'type': 'wait',
                'duration': 3.0,
                'description': 'Wait for initial boot and menu display'
            },
            {
                'type': 'capture',
                'name': 'startup_menu',
                'description': 'Initial menu screen after boot'
            },
        ],
        
        'menu_navigation': [
            {
                'type': 'wait',
                'duration': 2.0,
                'description': 'Wait for menu to load'
            },
            {
                'type': 'capture',
                'name': 'menu_initial',
                'description': 'Menu at startup'
            },
            {
                'type': 'button',
                'button': 4,
                'duration': 0.1,
                'description': 'Press DOWN button'
            },
            {
                'type': 'wait',
                'duration': 0.3,
                'description': 'Wait for menu to update'
            },
            {
                'type': 'capture',
                'name': 'menu_down_1',
                'description': 'Menu after one down press'
            },
            {
                'type': 'button',
                'button': 4,
                'duration': 0.1,
                'description': 'Press DOWN button again'
            },
            {
                'type': 'wait',
                'duration': 0.3,
                'description': 'Wait for menu to update'
            },
            {
                'type': 'capture',
                'name': 'menu_down_2',
                'description': 'Menu after two down presses'
            },
            {
                'type': 'button',
                'button': 5,
                'duration': 0.1,
                'description': 'Press UP button'
            },
            {
                'type': 'wait',
                'duration': 0.3,
                'description': 'Wait for menu to update'
            },
            {
                'type': 'capture',
                'name': 'menu_up_1',
                'description': 'Menu after up press'
            },
        ],
        
        'app_launch': [
            {
                'type': 'wait',
                'duration': 2.0,
                'description': 'Wait for menu'
            },
            {
                'type': 'button',
                'button': 6,
                'duration': 0.1,
                'description': 'Press SELECT button to launch app'
            },
            {
                'type': 'wait',
                'duration': 2.0,
                'description': 'Wait for app to load'
            },
            {
                'type': 'capture',
                'name': 'app_running',
                'description': 'App after launch'
            },
            {
                'type': 'wait',
                'duration': 3.0,
                'description': 'Wait for app animation/updates'
            },
            {
                'type': 'capture',
                'name': 'app_running_after_3s',
                'description': 'App after 3 seconds of runtime'
            },
        ],
        
        'dual_display': [
            {
                'type': 'wait',
                'duration': 3.0,
                'description': 'Wait for displays to initialize'
            },
            {
                'type': 'capture',
                'name': 'dual_display_state',
                'description': 'Both displays showing content'
            },
        ],
        
        'button_response': [
            {
                'type': 'wait',
                'duration': 2.0,
                'description': 'Wait for menu'
            },
            {
                'type': 'capture',
                'name': 'before_button_test',
                'description': 'State before button presses'
            },
            {
                'type': 'button',
                'button': 1,
                'duration': 0.1,
                'description': 'Test button 1'
            },
            {
                'type': 'wait',
                'duration': 0.5,
                'description': 'Wait for response'
            },
            {
                'type': 'capture',
                'name': 'after_button_1',
                'description': 'State after button 1'
            },
            {
                'type': 'button',
                'button': 2,
                'duration': 0.1,
                'description': 'Test button 2'
            },
            {
                'type': 'wait',
                'duration': 0.5,
                'description': 'Wait for response'
            },
            {
                'type': 'capture',
                'name': 'after_button_2',
                'description': 'State after button 2'
            },
        ],
    }
    
    return sequences


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='AI-driven regression test for badge simulator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Run test suite
  %(prog)s --create-baseline        # Create baseline screenshots
  %(prog)s --compare                # Run tests and compare to baseline
  %(prog)s --test startup           # Run specific test sequence
  %(prog)s --config dev.json        # Use custom simulator config
        """
    )
    
    parser.add_argument('--create-baseline', action='store_true',
                       help='Create baseline screenshots (first-time setup)')
    parser.add_argument('--compare', action='store_true',
                       help='Compare screenshots to baseline')
    parser.add_argument('--test', type=str,
                       help='Run specific test sequence (default: all)')
    parser.add_argument('--config', type=str, default='config.json',
                       help='Simulator config file (default: config.json)')
    parser.add_argument('--no-simulator', action='store_true',
                       help='Skip simulator startup (assume already running)')
    
    args = parser.parse_args()
    
    # Create test instance
    test = RegressionTest(
        config_path=args.config,
        baseline_mode=args.create_baseline,
        compare_mode=args.compare
    )
    
    try:
        # Start simulator unless skipped
        if not args.no_simulator:
            if not test.start_simulator():
                print("\n✗ Failed to start simulator")
                return 1
        else:
            print("Using existing simulator instance...")
            if not test.client.connect():
                print("✗ Could not connect to running simulator")
                return 1
        
        # Get test sequences
        sequences = define_test_sequences()
        
        # Determine which tests to run
        if args.test:
            if args.test not in sequences:
                print(f"✗ Unknown test sequence: {args.test}")
                print(f"Available: {', '.join(sequences.keys())}")
                return 1
            tests_to_run = {args.test: sequences[args.test]}
        else:
            tests_to_run = sequences
        
        # Run tests
        print(f"\n{'='*60}")
        print(f"Running {len(tests_to_run)} test sequence(s)")
        if args.create_baseline:
            print("MODE: Creating baseline screenshots")
        elif args.compare:
            print("MODE: Testing with comparison to baseline")
        else:
            print("MODE: Testing without comparison")
        print(f"{'='*60}")
        
        all_passed = True
        for name, steps in tests_to_run.items():
            if not test.run_test_sequence(name, steps):
                all_passed = False
        
        # Compare if requested
        comparison_results = {}
        if args.compare and not args.create_baseline:
            comparison_results = test.compare_screenshots()
        
        # Generate report
        success = test.generate_report(comparison_results)
        
        if success:
            print("\n✓ All tests passed!")
            return 0
        else:
            print("\n✗ Some tests failed")
            return 1
            
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        return 1
    except Exception as e:
        print(f"\n✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if not args.no_simulator:
            test.stop_simulator()


if __name__ == '__main__':
    import os
    sys.exit(main())
