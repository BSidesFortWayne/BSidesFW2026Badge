# Regression Test Guide

The badge simulator includes an AI-driven regression test system that automates visual testing by capturing screenshots at various UI states and comparing them to baseline images.

## Overview

The regression test system:
- **Automates simulator startup and shutdown**
- **Captures screenshots** at defined test points
- **Compares visual changes** between test runs
- **Generates detailed reports** with metrics
- **Supports manual interaction** for button presses (current limitation)

## Quick Start

### 1. Create Baseline (First Time)

Create reference screenshots for comparison:

```bash
cd simulator/
./regression_test.py --create-baseline
```

**During the test:**
- The simulator will start automatically
- Follow the on-screen prompts to press buttons at specific times
- Screenshots are saved to `regression_tests/baseline/`

### 2. Run Tests with Comparison

Run tests and compare to baseline:

```bash
./regression_test.py --compare
```

**What happens:**
- Simulator starts
- Test sequences run and capture screenshots
- Screenshots are compared to baseline
- Visual differences are highlighted
- Report is generated

### 3. Run Specific Test

Run a single test sequence:

```bash
./regression_test.py --test startup
./regression_test.py --test menu_navigation
./regression_test.py --test app_launch
./regression_test.py --test dual_display
```

## Test Sequences

### Available Sequences

1. **startup** - Tests initial boot and menu display
2. **menu_navigation** - Tests navigating through the menu with up/down buttons
3. **app_launch** - Tests launching and running an app
4. **dual_display** - Tests both displays showing content

### Manual Interaction Required

The simulator doesn't currently support programmatic button presses via the JSON protocol. During tests, you'll see prompts like:

```
Manual: Press DOWN button (key 4)
```

When you see these prompts:
1. Focus on the simulator window
2. Press the indicated keyboard key
3. Wait for the next step

**Button Key Mapping:**
- `0` - Boot/Reset (SW5)
- `1-4` - SW1-SW4 (top buttons)
- `4` - DOWN button
- `5` - UP button
- `6` - SELECT button
- `7-9` - Game buttons

## Visual Comparison

When running with `--compare`, the test system:

1. **Loads baseline** images from `regression_tests/baseline/`
2. **Captures current** screenshots to `regression_tests/current/`
3. **Calculates RMS** (Root Mean Square) difference per image
4. **Generates diff images** for significant differences
5. **Saves diffs** to `regression_tests/diffs/`

### RMS Threshold

- **RMS < 1.0** - Images match (minor differences from anti-aliasing, etc.)
- **RMS > 1.0** - Significant visual difference detected

### Reading Diff Images

Diff images show pixel-by-pixel differences:
- **Black** - Pixels match
- **Bright colors** - Pixels differ (enhanced 10x for visibility)

## Command-Line Options

```bash
./regression_test.py [OPTIONS]

Options:
  --create-baseline       Create baseline screenshots (first-time setup)
  --compare               Compare screenshots to baseline
  --test SEQUENCE         Run specific test sequence
  --config FILE           Use custom simulator config (default: config.json)
  --no-simulator          Skip simulator startup (use running instance)
  -h, --help              Show help message
```

## Usage Examples

### Initial Setup
```bash
# Create baseline with custom config
./regression_test.py --create-baseline --config dev_config.json
```

### Daily Testing
```bash
# Quick test without comparison
./regression_test.py

# Full test with visual comparison
./regression_test.py --compare
```

### Testing Specific Features
```bash
# Test just menu navigation
./regression_test.py --test menu_navigation --compare

# Test app launch without starting simulator
./regression_test.py --test app_launch --no-simulator
```

### CI/CD Integration
```bash
# Automated testing in CI pipeline
./regression_test.py --compare
if [ $? -ne 0 ]; then
    echo "Visual regression detected!"
    exit 1
fi
```

## Test Report

After each test run, a JSON report is generated in `regression_tests/`:

```json
{
  "timestamp": "20250112_143052",
  "mode": "test",
  "config": "config.json",
  "test_results": [...],
  "comparison_results": {...},
  "summary": {
    "total_captures": 8,
    "successful_captures": 8,
    "failed_captures": 0,
    "total_comparisons": 8,
    "matches": 7,
    "differences": 1,
    "errors": 0
  }
}
```

**Fields:**
- `test_results` - Capture details for each screenshot
- `comparison_results` - RMS values and diff paths
- `summary` - High-level test metrics

## Directory Structure

```
simulator/
├── regression_test.py          # Main test script
├── regression_tests/           # Test outputs
│   ├── baseline/               # Reference screenshots
│   │   ├── startup_menu.png
│   │   ├── menu_initial.png
│   │   └── ...
│   ├── current/                # Latest test screenshots
│   │   └── ...
│   ├── diffs/                  # Visual difference images
│   │   ├── menu_down_1_diff.png
│   │   └── ...
│   └── report_*.json           # Test reports
```

## Troubleshooting

### "Connection refused" error
- Ensure simulator isn't already running on port 4455
- Check that config file exists and is valid
- Try manually starting simulator first, then use `--no-simulator`

### Screenshots are identical when they shouldn't be
- Ensure you're interacting with the simulator during test pauses
- Check that the app is actually rendering changes
- Verify sufficient wait time between captures

### Diff images show noise but UI looks the same
- Anti-aliasing and sub-pixel rendering can cause minor RMS differences
- Font rendering may vary slightly between runs
- Consider this normal if RMS is very low (< 0.5)

### Baseline is outdated
- Delete `regression_tests/baseline/`
- Run `--create-baseline` again
- Or manually replace specific baseline images

## Future Enhancements

### Planned Features

1. **Automated button presses** - Programmatic control via simulator JSON protocol
2. **Video recording** - Capture test sequences as video
3. **Parallel testing** - Run multiple simulators simultaneously
4. **ML-based comparison** - Semantic visual comparison beyond pixel diffs
5. **Performance metrics** - Capture FPS, memory usage, etc.
6. **Test templates** - Define tests in YAML/JSON files
7. **Web dashboard** - View test results in browser

### Contributing Test Sequences

To add new test sequences, edit `regression_test.py` and add to `define_test_sequences()`:

```python
'my_new_test': [
    {
        'type': 'wait',
        'duration': 2.0,
        'description': 'Wait for something'
    },
    {
        'type': 'capture',
        'name': 'my_screenshot',
        'description': 'Description of state'
    },
],
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Visual Regression Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install dependencies
        run: |
          cd simulator
          pip install -r requirements.txt
          sudo apt-get install -y xvfb
      
      - name: Run regression tests
        run: |
          cd simulator
          xvfb-run ./regression_test.py --compare
      
      - name: Upload artifacts
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: regression-diffs
          path: simulator/regression_tests/diffs/
```

### Using xvfb for Headless Testing

Since the simulator uses pygame (GUI), use xvfb for headless environments:

```bash
# Install xvfb
sudo apt-get install xvfb

# Run with virtual display
xvfb-run ./regression_test.py --compare
```

## Best Practices

1. **Update baseline regularly** - When intentional UI changes are made
2. **Review diffs carefully** - Not all differences are bugs
3. **Test in consistent environment** - Same display resolution, fonts, etc.
4. **Document baseline creation** - Note the app versions and settings used
5. **Commit baseline images** - Track them in version control
6. **Automate in CI** - Run tests on every commit
7. **Set RMS thresholds** - Adjust based on your tolerance for variation

## API Usage

The `regression_test.py` script can be imported and used in other Python scripts:

```python
from regression_test import SimulatorClient, RegressionTest

# Use simulator client directly
client = SimulatorClient()
client.connect()
screenshot_path = client.take_screenshot('my_test.png')

# Use full test framework
test = RegressionTest(baseline_mode=True)
test.start_simulator()
test.capture_state('test_state', 'Description here')
test.stop_simulator()
```

## Comparison to Browser Testing Tools

Like browser-based visual regression tools (Percy, Applitools, BackstopJS), this system provides:

✅ **Automated screenshot capture**  
✅ **Visual diff generation**  
✅ **Baseline management**  
✅ **CI/CD integration**  
✅ **Test reporting**  

**Advantages:**
- No cloud dependency
- No subscription costs
- Full control over comparison algorithm
- Hardware mock state visible in screenshots

**Disadvantages:**
- Manual button interaction required (for now)
- Less sophisticated ML-based comparison
- No multi-browser/platform testing

## Related Documentation

- [SCREENSHOT_GUIDE.md](SCREENSHOT_GUIDE.md) - Screenshot capture details
- [SIMULATOR_USER_GUIDE.md](../docs/SIMULATOR_USER_GUIDE.md) - General simulator usage
- [take_screenshot.py](take_screenshot.py) - Screenshot utility source

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review simulator logs in `logs/` directory
3. Run with verbose output: `--config config.json` (with debug enabled)
4. Open an issue with report JSON and diff images
