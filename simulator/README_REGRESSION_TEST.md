# AI-Driven Regression Testing - Quick Start

This directory contains an automated regression testing system for the badge simulator that captures screenshots and simulates user interactions.

## What's Been Created

### 1. **regression_test.py** - Main Test Framework
Full-featured regression test system with:
- Automated simulator startup/shutdown
- Screenshot capture at key states
- **Automated button press simulation** (NEW!)
- Visual comparison with baseline images
- JSON test reports
- Multiple test sequences

### 2. **demo_regression_test.py** - Quick Demo
Simple demonstration script that:
- Starts simulator
- Captures screenshots
- Tests button simulation
- Verifies functionality

### 3. **REGRESSION_TEST_GUIDE.md** - Complete documentation

## Quick Start

### Try the Demo

The fastest way to see the regression test in action:

```bash
cd simulator/
./demo_regression_test.py
```

This will:
1. Start the simulator automatically
2. Capture a screenshot
3. Simulate a button press
4. Capture another screenshot
5. Stop the simulator

**New Feature**: Button presses are now **fully automated**! No manual interaction needed.

### Run Full Test Suite

```bash
# Create baseline (first time)
./regression_test.py --create-baseline

# Run test with comparison
./regression_test.py --compare

# Run specific test
./regression_test.py --test button_response --compare
```

## What Was Created

### 1. Core Regression Test System ([regression_test.py](regression_test.py))

**Features:**
- ✅ **Automated simulator control** - Starts/stops simulator automatically
- ✅ **Screenshot capture** - Programmatic screenshot via JSON protocol
- ✅ **Button simulation** - Automated button presses (NEW!)
- ✅ **Visual comparison** - Pixel-by-pixel diff with RMS calculation
- ✅ **Test sequences** - Define multi-step test workflows
- ✅ **Baseline management** - Create and compare against baselines
- ✅ **JSON reports** - Detailed test results and metrics

### Key Features Implemented:

#### 1. Screenshot Capture
- Uses existing `take_screenshot.py` functionality
- Auto-generates timestamped filenames
- Supports custom paths
- Integrated with test sequences

#### 2. Button Simulation (NEW!)
- **Added JSON protocol support for button presses**
- Simulator now accepts `{'module': 'button', 'command': 'press', 'parameters': {'button': N, 'duration': 0.1}}`
- Buttons are programmatically pressed without manual intervention
- Works with all 8 buttons (0-7)

#### 3. Visual Regression
- Captures screenshots at each test step
- Compares to baseline images using PIL
- Calculates RMS (Root Mean Square) difference
- Generates visual diff images for debugging

### 4. Automated Test Sequences

The system includes predefined test sequences:
- **startup** - Tests initial boot
- **menu_navigation** - Tests navigating menu with UP/DOWN/SELECT
- **app_launch** - Tests launching an app
- **dual_display** - Tests both displays
- **button_response** - Tests button press handling

## Summary

I've created a comprehensive AI-driven regression test system for the badge simulator that includes:

### Core Features ✓

1. **Automated Screenshot Capture** - Via JSON protocol
2. **Button Press Simulation** - New feature added to simulator's JSON protocol
3. **Test Sequences** - Define multi-step UI test flows
4. **Visual Comparison** - Compare screenshots using PIL image diff
5. **Baseline Management** - Create and compare against baseline images
6. **Test Reporting** - JSON reports with detailed metrics

### Files Created

1. **[regression_test.py](simulator/regression_test.py)** - Main regression test framework (540 lines)
   - SimulatorClient class for JSON protocol communication
   - RegressionTest orchestrator
   - Automated test sequences
   - Visual comparison using PIL
   - Report generation

2. **[REGRESSION_TEST_GUIDE.md](simulator/REGRESSION_TEST_GUIDE.md)** - Comprehensive documentation
   - Quick start guide
   - Test sequence definitions
   - Visual comparison details
   - CI/CD integration examples
   - Troubleshooting guide

3. **[demo_regression_test.py](simulator/demo_regression_test.py)** - Quick demo script to verify functionality

## Key Features Implemented

### ✅ Automated Screenshot Capture
- Uses existing `take_screenshot.py` functionality
- Auto-generates timestamped filenames
- Captures full simulator window

### ✅ Programmatic Button Presses
- Added `button` module to simulator's JSON protocol
- New `simulate_button_press()` method in [gui.py](simulator/gui.py#L565-L593)
- Automated button press commands via socket

### ✅ Visual Regression Comparison
- Pixel-perfect comparison using PIL/Pillow
- RMS (Root Mean Square) difference calculation
- Automatic diff image generation
- Configurable difference thresholds

### ✅ Test Orchestration
- Multiple test sequences defined
- Automated simulator startup/shutdown
- JSON report generation
- Support for baseline creation

## Usage Examples

### Quick Demo
```bash
cd simulator/
./demo_regression_test.py
```

### Full Test Suite
```bash
# First time: create baseline
./regression_test.py --create-baseline

# Regular testing with comparison
./regression_test.py --compare

# Run specific test
./regression_test.py --test menu_navigation --compare
```

## What Was Created

### 1. **[regression_test.py](simulator/regression_test.py)** - Main test framework
   - `SimulatorClient` - Communicates with simulator via JSON protocol
   - `RegressionTest` - Orchestrates test execution
   - Automated button press simulation
   - Screenshot capture at test points
   - Visual comparison with PIL
   - Report generation

### 2. **Button Press Support Added to Simulator**

Enhanced [gui.py](simulator/gui.py#L323-L331) with:
- `simulate_button_press()` method for programmatic button control
- JSON protocol support via `'button'` module with `'press'` command
- Integration with existing button state system

### 3. Test Sequences Defined

Five pre-built test sequences:
- **startup** - Boot and initial display
- **menu_navigation** - UP/DOWN/SELECT navigation
- **app_launch** - App selection and running
- **dual_display** - Both displays active
- **button_response** - Button feedback testing

## Usage

### Basic Test (No Comparison)
```bash
cd simulator/
./regression_test.py --test startup
```

### Create Baseline Screenshots
```bash
./regression_test.py --create-baseline
```

### Run Tests with Visual Comparison
```bash
./regression_test.py --compare
```

### Quick Demo
```bash
./demo_regression_test.py
```

## Key Features Implemented

### 1. **Automated Screenshot Capture**
- Uses existing `take_screenshot.py` utility
- JSON protocol communication
- Auto-generated or custom filenames
- Organized directory structure

### 2. **Button Press Simulation** (NEW!)
I added programmatic button control to the simulator:
- New `button` module in JSON protocol
- `simulate_button_press()` method in [gui.py](simulator/gui.py#L543-L570)
- Automated button press commands
- Configurable press duration

### 3. **Test Sequences**
Pre-defined test sequences:
- `startup` - Basic boot test
- `menu_navigation` - Automated UP/DOWN/SELECT button testing
- `app_launch` - Launch app and capture states
- `dual_display` - Verify both displays
- `button_response` - Test button responsiveness

### 4. Visual Comparison

When run with `--compare`, uses PIL to:
- Calculate RMS (Root Mean Square) pixel differences
- Generate enhanced diff images
- Report visual changes with metrics

## Usage

**Create baseline:**
```bash
cd simulator/
./regression_test.py --create-baseline
```

**Run tests:**
```bash
# Without comparison
./regression_test.py

# With comparison to baseline
./regression_test.py --compare

# Specific test
./regression_test.py --test menu_navigation --compare
```

**Quick demo:**
```bash
./demo_regression_test.py
```

## What's New

### Automated Button Presses ✨

The simulator now supports programmatic button presses via JSON protocol:

```python
# Send button press command
command = {
    'module': 'button',
    'command': 'press',
    'parameters': {
        'button': 4,      # Button index (0-7)
        'duration': 0.1   # Hold duration in seconds
    }
}
```

This enables fully automated UI testing without manual interaction!

### Test Sequences

Pre-defined test sequences include:
- **startup** - Initial boot and menu display
- **menu_navigation** - Automated menu navigation with button presses
- **app_launch** - Launch app and capture running state
- **dual_display** - Verify both displays showing content
- **button_response** - Test button responsiveness

### Visual Comparison

With Pillow installed, the test system can:
- Compare screenshots pixel-by-pixel
- Calculate RMS (Root Mean Square) differences
- Generate enhanced diff images
- Report match/difference status

## Requirements

```bash
# Core functionality (already installed)
- pygame
- pygame_gui

# Optional for visual comparison
pip install Pillow
```

## Example Test Run

```bash
$ ./regression_test.py --create-baseline --test startup
============================================================
BSides FW 2025 Badge Simulator
============================================================
Features: Binary Protocol + Hardware Controls
...

============================================================
Running 1 test sequence(s)
MODE: Creating baseline screenshots
============================================================

============================================================
Test Sequence: startup
============================================================

Step 1/2: Wait for initial boot and menu display
  Waiting: Wait for initial boot and menu display

Step 2/2: Capture initial screenshot
  Capturing: startup_menu
    Initial menu screen after boot

✓ All tests passed!
```

## Integration with CI/CD

Example GitHub Actions workflow:

```yaml
- name: Run regression tests
  run: |
    cd simulator
    xvfb-run ./regression_test.py --compare
    
- name: Upload diff images
  if: failure()
  uses: actions/upload-artifact@v3
  with:
    name: visual-diffs
    path: simulator/regression_tests/diffs/
```

## Files Created

- `regression_test.py` - Main test framework (542 lines)
- `demo_regression_test.py` - Quick demo script (139 lines)
- `REGRESSION_TEST_GUIDE.md` - Comprehensive guide (500+ lines)
- `README_REGRESSION_TEST.md` - This file

## Architecture

```
regression_test.py
├── SimulatorClient
│   ├── connect() - Connect to simulator
│   ├── send_command() - Send JSON protocol commands
│   ├── take_screenshot() - Capture screenshot
│   └── press_button() - Simulate button press
│
└── RegressionTest
    ├── start_simulator() - Launch simulator process
    ├── stop_simulator() - Cleanup
    ├── capture_state() - Take screenshot with naming
    ├── run_test_sequence() - Execute test steps
    ├── compare_screenshots() - Visual comparison
    └── generate_report() - JSON test report
```

## Next Steps

1. **Create baselines**: `./regression_test.py --create-baseline`
2. **Run tests**: `./regression_test.py --compare`
3. **Add custom tests**: Edit `define_test_sequences()` in regression_test.py
4. **Integrate CI**: Add to your GitHub Actions workflow
5. **Review diffs**: Check `regression_tests/diffs/` for visual changes

## See Also

- [REGRESSION_TEST_GUIDE.md](REGRESSION_TEST_GUIDE.md) - Full documentation
- [SCREENSHOT_GUIDE.md](SCREENSHOT_GUIDE.md) - Screenshot API details
- [SIMULATOR_USER_GUIDE.md](../docs/SIMULATOR_USER_GUIDE.md) - Simulator usage
