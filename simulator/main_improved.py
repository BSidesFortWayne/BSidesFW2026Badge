#!/usr/bin/env python3
"""
BSides FW 2025 Badge Simulator - Main Entry Point

Improved Phase 0 version with:
- Configuration file support
- Structured logging
- Better error handling
- Output capture for AI analysis
"""

import shutil
import subprocess
import argparse
import socket
import json
import os
import sys
import threading
import time
from pathlib import Path

import gui
from logger import create_logger


def load_config(config_path: str = 'config.json') -> dict:
    """Load configuration from file"""
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='BSides FW 2025 Badge Simulator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Use defaults from config.json
  %(prog)s -p ../src                # Specify project directory
  %(prog)s -p ../src -v             # Verbose output
  %(prog)s --config myconfig.json   # Use custom config file
        """
    )
    
    parser.add_argument('-p', '--project', type=str, 
                       help='Project directory containing main.py')
    parser.add_argument('-m', '--micropython', type=str,
                       help='MicroPython executable path')
    parser.add_argument('-c', '--config', type=str, default='config.json',
                       help='Configuration file (default: config.json)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose output')
    parser.add_argument('--no-gui', action='store_true',
                       help='Run without GUI (testing mode)')
    parser.add_argument('--port', type=int,
                       help='Socket port (default: from config or 4455)')
    parser.add_argument('--no-logs', action='store_true',
                       help='Disable logging to files')
    
    return parser.parse_args()


def validate_paths(project_path: str, micropython_path: str, logger) -> bool:
    """Validate required paths exist"""
    
    # Check project directory
    project_main = os.path.join(project_path, 'main.py')
    if not os.path.exists(project_main):
        logger.log_error('validation', f'No main.py found in project directory: {project_path}')
        return False
    
    # Check MicroPython executable
    if shutil.which(micropython_path) is None:
        logger.log_error('validation', 
                        f'MicroPython executable not found: {micropython_path}',
                        hint='Try: apt install micropython, or build from source')
        return False
    
    # Check libraries directory
    if not os.path.exists('libraries'):
        logger.log_error('validation', 'libraries/ directory not found',
                        hint='Make sure you run from simulator/ directory')
        return False
    
    return True


def setup_project_directory(project_path: str, logger):
    """Copy project files and overlay simulator libraries"""
    logger.log_info('Setting up project directory...')
    
    # Clean old src directory
    if os.path.exists('src'):
        logger.log_info('Removing old src/ directory')
        shutil.rmtree('src')
    
    # Copy project files
    logger.log_info(f'Copying project from {project_path}')
    shutil.copytree(project_path, 'src')
    
    # Overlay simulator libraries (shims)
    logger.log_info('Overlaying simulator libraries')
    shutil.copytree('libraries', 'src', dirs_exist_ok=True)
    
    # Set environment variable for simulator detection
    os.environ['BADGE_SIMULATOR'] = '1'
    logger.log_info('Set BADGE_SIMULATOR=1 environment variable')


def create_socket_server(host: str, port: int, logger):
    """Create and bind socket server"""
    logger.log_info(f'Creating socket server on {host}:{port}')
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen()
        logger.log_info(f'Socket server listening on {host}:{port}')
        return sock
    except OSError as e:
        logger.log_error('socket', f'Failed to bind socket: {e}',
                        hint='Port may be in use. Try a different port with --port')
        return None


def start_micropython(micropython_path: str, logger):
    """Start MicroPython process"""
    logger.log_info(f'Starting MicroPython: {micropython_path}')
    
    try:
        process = subprocess.Popen(
            [micropython_path, '-X', 'heapsize=8M', 'main.py'],
            cwd='src',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1  # Line buffered
        )
        
        logger.log_info(f'MicroPython process started (PID: {process.pid})')
        return process
        
    except FileNotFoundError:
        logger.log_error('micropython', f'Failed to start MicroPython: {micropython_path}',
                        hint='Check that micropython is installed and path is correct')
        return None
    except Exception as e:
        logger.log_error('micropython', f'Unexpected error starting MicroPython: {e}')
        return None


def stream_micropython_output(process, logger):
    """Stream MicroPython stdout and stderr to logger"""
    
    def stream_output(stream, stream_name):
        for line in stream:
            logger.log_micropython(line, stream_name)
    
    # Start threads for stdout and stderr
    stdout_thread = threading.Thread(
        target=stream_output,
        args=(process.stdout, 'stdout'),
        daemon=True
    )
    stderr_thread = threading.Thread(
        target=stream_output,
        args=(process.stderr, 'stderr'),
        daemon=True
    )
    
    stdout_thread.start()
    stderr_thread.start()
    
    return stdout_thread, stderr_thread


def handle_communication(emulator_socket, gui_instance, micropython_process, logger):
    """Handle communication between MicroPython and GUI"""
    
    logger.log_info('Waiting for MicroPython to connect...')
    
    try:
        # Wait for connection with timeout
        emulator_socket.settimeout(10.0)
        emulator_conn, addr = emulator_socket.accept()
        emulator_socket.settimeout(None)
        logger.log_info(f'MicroPython connected from {addr}')
        
    except socket.timeout:
        logger.log_error('connection', 'Timeout waiting for MicroPython connection',
                        hint='MicroPython may have crashed during startup')
        return None
    
    def receive_commands():
        """Thread to receive commands from MicroPython"""
        buffer = b''
        while gui_instance.running:
            try:
                # Receive data in chunks
                chunk = emulator_conn.recv(65536)  # Larger buffer for framebuffer data
                if not chunk:
                    logger.log_warning('Connection closed by MicroPython')
                    break
                
                buffer += chunk
                
                # Try to parse JSON - keep accumulating if incomplete
                try:
                    data = json.loads(buffer.decode('utf-8'))
                    buffer = b''  # Clear buffer on successful parse
                    
                    # Log command
                    logger.log_command(data)
                    
                    # Handle command
                    resp = gui_instance.handle_command(data)
                    
                    # Send response
                    data_to_send = {'status': 'ok', 'resp': resp}
                    emulator_conn.send(json.dumps(data_to_send).encode())
                    
                except json.JSONDecodeError:
                    # Incomplete JSON, continue accumulating
                    # But check if buffer is getting too large
                    if len(buffer) > 10 * 1024 * 1024:  # 10MB sanity limit
                        logger.log_error('protocol', f'Buffer overflow: {len(buffer)} bytes')
                        buffer = b''
                    continue
                    
            except BrokenPipeError:
                logger.log_warning('Connection broken')
                break
            except Exception as e:
                logger.log_error('communication', f'Error in receive loop: {e}')
                break
        
        # Cleanup
        logger.log_info('Terminating MicroPython process')
        micropython_process.terminate()
        
        # Wait for process to end
        try:
            micropython_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.log_warning('MicroPython did not terminate, killing')
            micropython_process.kill()
    
    return receive_commands


def main():
    """Main entry point"""
    
    # Parse arguments
    args = parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Override config with command line args
    if args.project:
        config['project_path'] = args.project
    if args.micropython:
        config['micropython_path'] = args.micropython
    if args.port:
        config['socket_port'] = args.port
    if args.verbose:
        config.setdefault('debug', {})['verbose'] = True
    if args.no_logs:
        config.setdefault('logging', {})['enabled'] = False
    
    # Get final configuration
    project_path = config.get('project_path', '../src')
    micropython_path = config.get('micropython_path', 'micropython')
    socket_host = config.get('socket_host', '127.0.0.1')
    socket_port = config.get('socket_port', 4455)
    
    # Create logger
    logger = create_logger(config)
    
    # Log startup
    logger.log_startup(
        project_path=project_path,
        micropython_path=micropython_path,
        socket=f'{socket_host}:{socket_port}',
        config_file=args.config
    )
    
    # Validate paths
    if not validate_paths(project_path, micropython_path, logger):
        logger.log_error('startup', 'Validation failed, exiting')
        return 1
    
    # Setup project directory
    try:
        setup_project_directory(project_path, logger)
    except Exception as e:
        logger.log_error('setup', f'Failed to setup project directory: {e}')
        return 1
    
    # Create socket server
    emulator_socket = create_socket_server(socket_host, socket_port, logger)
    if not emulator_socket:
        return 1
    
    # Start MicroPython
    micropython_process = start_micropython(micropython_path, logger)
    if not micropython_process:
        emulator_socket.close()
        return 1
    
    # Stream MicroPython output
    stream_micropython_output(micropython_process, logger)
    
    # Create GUI
    logger.log_info('Initializing GUI...')
    gui_instance = gui.GUI(config, logger)
    
    # Setup communication handler
    receive_commands = handle_communication(
        emulator_socket,
        gui_instance,
        micropython_process,
        logger
    )
    
    if not receive_commands:
        micropython_process.terminate()
        emulator_socket.close()
        return 1
    
    # Start communication thread
    comm_thread = threading.Thread(target=receive_commands, daemon=True)
    comm_thread.start()
    
    # Run GUI (blocks until closed)
    logger.log_info('Starting GUI main loop')
    try:
        gui_instance.gameloop()
    except KeyboardInterrupt:
        logger.log_info('Keyboard interrupt received')
    except Exception as e:
        logger.log_error('gui', f'GUI error: {e}')
        import traceback
        traceback.print_exc()
    
    # Cleanup
    logger.log_info('Shutting down simulator')
    emulator_socket.close()
    
    logger.log_info('Simulator stopped')
    return 0


if __name__ == '__main__':
    sys.exit(main())
