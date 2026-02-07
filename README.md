# 🕐 Hilan Attendance Auto-Fill

A CLI tool to automatically fill your attendance hours on Hilan (HilanNet) website using Python and Playwright.

Intelligently skips existing records and supports flexible work patterns. Includes dry-run preview, shell completions, and a beautiful Rich-powered CLI.

## 📦 Installation

### From GitHub Releases (recommended)

Download the latest `.whl` file from [Releases](https://github.com/ronharel02/hilan-attendance/releases), and install it:

```bash
pip install hilan_attendance-*.whl
hilan init
```

### From source

```bash
git clone https://github.com/ronharel02/hilan-attendance.git
cd hilan-attendance
pip install .
hilan init
```

## 🚀 Quick Start

### 1. Initialize configuration

```bash
hilan init
```

This will interactively create your config file at `~/.config/hilan-attendance.json` (see the [Configuration](#️-configuration) section).

### 2. Check attendance status

```bash
hilan status
```

### 3. Fill attendance

```bash
# Fill current pay period
hilan fill

# Preview changes without submitting
hilan fill --dry-run
```

## 📖 Commands

All commands support `-h` or `--help` for usage info.

Use `-c` on the main command to specify a custom config file:

```bash
hilan -c ./my-config.json status
```

### `hilan init`

Create your configuration file and install the playwright browser.

```bash
hilan init                      # Create new config
hilan init --force              # Overwrite existing config
hilan init --skip-completions   # Skip shell completion setup
```

### `hilan status`

View current attendance status without making changes.

```bash
hilan status                    # Current pay period
hilan status -m 11 -y 2024      # Specific month (November 2024)
```

### `hilan fill`

Fill attendance for a pay period.

```bash
hilan fill                      # Fill current pay period
hilan fill -m 11 -y 2024        # Fill November 2024 pay period
hilan fill --today              # Fill today if needed
hilan fill --up-to-today        # Fill all days up to and including today
hilan fill --dry-run            # Preview without making changes
```

## ⚙️ Configuration

### Config file location

`~/.config/hilan-attendance.json`

### Configuration options

| Field | Description | Default |
| ----- | ----------- | ------- |
| `username` | Your Hilan username | *(required)* |
| `password` | Your Hilan password | *(required)* |
| `url` | Hilan base URL (e.g., `https://yourcompany.hilan.co.il`) | *(required)* |
| `pattern.entry_time` | Default entry time | `09:00` |
| `pattern.exit_time` | Default exit time | `18:00` |
| `pattern.days` | Work type per day of week | See below |
| `headless` | Run browser without UI | `true` |
| `slow_mo` | Slow down actions (ms) | `500` |
| `pay_period_start_day` | Day of month when pay period starts | `20` |

### Work types

| Type | Description | Hilan term |
| ---- | ----------- | ---------- |
| `office` | Working from office | עבודה מהמשרד |
| `home` | Working from home | עבודה מהבית |
| `skip` | Don't fill this day | - |

### Pattern days

Configure which days to fill and with what work type:

```json
"pattern": {
  "entry_time": "09:00:00",
  "exit_time": "18:00:00",
  "days": {
    "sunday": "office",
    "monday": "home",
    "tuesday": "office",
    "wednesday": "office",
    "thursday": "office"
  }
}
```

Days not listed (e.g., Friday, Saturday) are treated as weekends and skipped.

### Pay period

Hilan uses pay periods that typically run from the 20th of one month to the 19th of the next (e.g., Nov 20 - Dec 19 is the "December" pay period). The `pay_period_start_day` setting controls this:

- Default is `20` (pay period runs 20th-19th)
- The tool automatically detects which pay period you're in based on today's date
- For example, on December 21st, the tool knows you're in the January pay period

### Example config (Israeli work week)

```json
{
  "username": "john.doe",
  "password": "secretpassword",
  "url": "https://acme.hilan.co.il",
  "pattern": {
    "entry_time": "09:00:00",
    "exit_time": "18:00:00",
    "days": {
      "sunday": "office",
      "monday": "home",
      "tuesday": "office",
      "wednesday": "office",
      "thursday": "office"
    }
  },
  "headless": true,
  "slow_mo": 500,
  "pay_period_start_day": 20
}
```

## ✅ Development

Run all project checks with:

```bash
hatch run check
```

This runs:

- `ruff format`.
- `ruff check`.
- `ty check`.

Build a wheel with:

```bash
hatch build -t wheel
```

## 🧑‍⚖️ License

MIT License - feel free to use and modify!

## ⚠️ Disclaimer

This tool is for personal use to automate repetitive tasks. Make sure you comply with your company's policies regarding attendance reporting. Always verify the filled data is accurate before submitting.
