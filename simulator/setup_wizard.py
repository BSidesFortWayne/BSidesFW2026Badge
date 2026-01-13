#!/usr/bin/env python3
"""
BSides FW 2025 Badge Simulator - Setup Wizard

Interactive setup for first-time users to configure the simulator.
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path


def print_header(text: str):
    """Print a formatted header"""
    print()
    print('=' * 60)
    print(text)
    print('=' * 60)
    print()


def print_step(step_num: int, total: int, text: str):
    """Print a step indicator"""
    print(f'\n[Step {step_num}/{total}] {text}')
    print('-' * 60)


def ask_yes_no(question: str, default: bool = True) -> bool:
    """Ask a yes/no question"""
    default_str = 'Y/n' if default else 'y/N'
    response = input(f'{question} [{default_str}]: ').strip().lower()
    
    if not response:
        return default
    return response in ['y', 'yes']


def ask_choice(question: str, choices: list, default: int = 0) -> int:
    """Ask user to choose from a list"""
    print(f'\n{question}')
    for i, choice in enumerate(choices):
        marker = ' (default)' if i == default else ''
        print(f'  {i + 1}. {choice}{marker}')
    
    while True:
        response = input(f'\nChoice [1-{len(choices)}]: ').strip()
        if not response:
            return default
        
        try:
            choice_idx = int(response) - 1
            if 0 <= choice_idx < len(choices):
                return choice_idx
        except ValueError:
            pass
        
        print(f'Invalid choice. Please enter a number between 1 and {len(choices)}.')


def ask_text(question: str, default: str = '') -> str:
    """Ask for text input"""
    if default:
        response = input(f'{question} [{default}]: ').strip()
        return response if response else default
    else:
        while True:
            response = input(f'{question}: ').strip()
            if response:
                return response
            print('This field is required.')


def check_dependency(name: str, import_name: str = None, command: str = None) -> bool:
    """Check if a dependency is installed"""
    if import_name:
        try:
            __import__(import_name)
            return True
        except ImportError:
            return False
    
    if command:
        return shutil.which(command) is not None
    
    return False


def install_dependency(name: str, package: str, pip: bool = True) -> bool:
    """Attempt to install a dependency"""
    if pip:
        print(f'Installing {name}...')
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
            print(f'✓ {name} installed successfully')
            return True
        except subprocess.CalledProcessError:
            print(f'✗ Failed to install {name}')
            return False
    else:
        print(f'Please install {name} manually:')
        print(f'  $ {package}')
        return False


def run_setup_wizard() -> int:
    """Run the interactive setup wizard"""
    
    print_header('BSides FW 2025 Badge Simulator - Setup Wizard')
    
    print('Welcome! This wizard will help you set up the simulator.')
    print()
    print('The simulator allows you to develop and test badge apps without')
    print('physical hardware. It runs your app code in MicroPython and displays')
    print('the output in a pygame window.')
    print()
    
    if not ask_yes_no('Continue with setup?'):
        print('Setup cancelled.')
        return 0
    
    # Step 1: Check dependencies
    print_step(1, 5, 'Checking Dependencies')
    
    dependencies = {
        'Python 3.8+': {'check': sys.version_info >= (3, 8), 'required': True},
        'pygame': {'import': 'pygame', 'package': 'pygame', 'required': True},
        'Pillow': {'import': 'PIL', 'package': 'Pillow', 'required': True},
        'MicroPython': {'command': 'micropython', 'required': True},
        'pygame-gui': {'import': 'pygame_gui', 'package': 'pygame-gui', 'required': False,
                      'note': 'Required for enhanced mode with hardware controls'},
    }
    
    missing_required = []
    missing_optional = []
    
    for name, dep in dependencies.items():
        if 'check' in dep:
            has_dep = dep['check']
        elif 'import' in dep:
            has_dep = check_dependency(name, import_name=dep['import'])
        elif 'command' in dep:
            has_dep = check_dependency(name, command=dep['command'])
        else:
            has_dep = False
        
        status = '✓' if has_dep else '✗'
        note = f" ({dep['note']})" if 'note' in dep and not has_dep else ''
        print(f'{status} {name}{note}')
        
        if not has_dep:
            if dep['required']:
                missing_required.append((name, dep))
            else:
                missing_optional.append((name, dep))
    
    # Offer to install missing dependencies
    if missing_required or missing_optional:
        print()
        if missing_required:
            print('⚠ Some required dependencies are missing!')
            
            if ask_yes_no('Attempt to install missing dependencies?'):
                for name, dep in missing_required:
                    if 'package' in dep:
                        install_dependency(name, dep['package'])
                    elif 'command' in dep:
                        print(f'\n{name} must be installed manually:')
                        if name == 'MicroPython':
                            print('  Option 1: apt install micropython')
                            print('  Option 2: uv run micropython')
                            print('  Option 3: Build from source: https://micropython.org/')
                        input('Press Enter when ready...')
        
        if missing_optional:
            print()
            print('Optional dependencies missing:')
            for name, dep in missing_optional:
                print(f'  - {name}: {dep.get("note", "")}')
            
            if ask_yes_no('Install optional dependencies?'):
                for name, dep in missing_optional:
                    if 'package' in dep:
                        install_dependency(name, dep['package'])
    else:
        print('\n✓ All dependencies are installed!')
    
    # Step 2: Select project directory
    print_step(2, 5, 'Project Configuration')
    
    # Try to auto-detect src directory
    default_project = '../src'
    if os.path.exists(default_project) and os.path.exists(os.path.join(default_project, 'main.py')):
        print(f'✓ Found project directory: {default_project}')
        project_path = default_project
    else:
        print('Could not auto-detect project directory.')
        project_path = ask_text('Enter path to project directory (containing main.py)',
                               default='../src')
    
    while not os.path.exists(os.path.join(project_path, 'main.py')):
        print(f'✗ No main.py found in {project_path}')
        project_path = ask_text('Enter path to project directory (containing main.py)')
    
    print(f'✓ Using project directory: {project_path}')
    
    # Step 3: MicroPython configuration
    print_step(3, 5, 'MicroPython Configuration')
    
    # Try to find MicroPython
    micropython_candidates = ['micropython', 'uv run micropython']
    micropython_path = None
    
    for candidate in micropython_candidates:
        if shutil.which(candidate.split()[0]):
            print(f'✓ Found MicroPython: {candidate}')
            micropython_path = candidate
            break
    
    if not micropython_path:
        print('Could not auto-detect MicroPython.')
        micropython_path = ask_text('Enter MicroPython command or path',
                                   default='micropython')
    
    print(f'✓ Using MicroPython: {micropython_path}')
    
    # Step 4: Confirm features
    print_step(4, 5, 'Simulator Features')
    
    print('\nThe unified simulator includes all features by default:')
    print()
    print('  \u2713 Binary protocol (10-20x faster than JSON)')
    print('  \u2713 Hardware control panel (mock accelerometer, battery, WiFi, Bluetooth)')
    print('  \u2713 Dual circular display rendering')
    print('  \u2713 Keyboard button controls')
    print('  \u2713 Structured logging')
    print()
    print('These can be disabled with --json-only or --no-enhanced flags if needed.')
    print()
    
    # Step 5: Save configuration
    print_step(5, 5, 'Save Configuration')
    
    config = {
        'project_path': project_path,
        'micropython_path': micropython_path,
        'socket_port': 4455,
        'socket_host': '127.0.0.1',
        'binary_protocol': True,
        'binary_port': 4456,
        'enhanced_gui': True,
        'logging': {
            'enabled': True,
            'output_dir': 'logs',
            'log_micropython': True,
            'log_gui_commands': False,
            'log_button_polling': False,
            'structured_output': True
        },
        'gui': {
            'window_title': 'BSides FW 2025 Badge Simulator',
            'show_fps': True,
            'target_fps': 60,
            'show_led_positions': True
        },
        'debug': {
            'verbose': False,
            'print_commands': False,
            'print_startup': True
        }
    }
    
    config_path = 'config.json'
    
    # Backup existing config
    if os.path.exists(config_path):
        if ask_yes_no(f'{config_path} already exists. Backup existing config?'):
            backup_path = f'{config_path}.backup'
            shutil.copy(config_path, backup_path)
            print(f'✓ Backed up to {backup_path}')
    
    # Save configuration
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f'✓ Configuration saved to {config_path}')
    
    # Summary
    print_header('Setup Complete!')
    
    print('Configuration Summary:')
    print(f'  Project: {project_path}')
    print(f'  MicroPython: {micropython_path}')
    print(f'  Features: All enabled (Binary Protocol + Hardware Controls)')
    print()
    print('To run the simulator:')
    print('  ./run.sh')
    print()
    print('Or directly:')
    print('  ./simulator.py')
    print()
    print('To disable features:')
    print('  ./simulator.py --json-only       # Disable binary protocol')
    print('  ./simulator.py --no-enhanced     # Disable hardware controls')
    print()
    print('For help:')
    print('  ./simulator.py --help')
    print()
    
    if ask_yes_no('Run simulator now?'):
        print()
        print('Starting simulator...')
        print()
        
        # Import and run main
        import simulator
        sys.argv = ['simulator.py']
        sys.argv.extend(['-p', project_path, '-m', micropython_path])
        
        return simulator.main()
    
    return 0


if __name__ == '__main__':
    sys.exit(run_setup_wizard())
