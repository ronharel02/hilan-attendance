"""Command-line interface for Hilan Attendance."""

from __future__ import annotations

import os
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional

import click
from click.shell_completion import CompletionItem
from rich.panel import Panel

from . import __version__, console, enable_debug_logging, logger
from .attendance import fetch_attendance_data, run_attendance_flow
from .browser import HilanBrowser
from .config import (
	config_exists,
	create_config_interactive,
	get_config_path,
	load_config,
	save_config,
)
from .display import display_current_status
from .vocabulary import Months


class MonthType(click.ParamType):
	"""Custom type that accepts month number (1-12) or name (case-insensitive, prefix match)."""

	name = 'month'

	def convert(
		self,
		value: str,
		param: Optional[click.Parameter],
		ctx: Optional[click.Context],
	) -> int:
		"""Convert month name or number to integer."""
		if isinstance(value, int):
			return value

		# Try as number first
		try:
			month_num = int(value)
			if 1 <= month_num <= 12:
				return month_num
			self.fail(f'Month must be 1-12, got {month_num}', param, ctx)
		except ValueError:
			pass

		# Try as name (prefix match, case-insensitive)
		value_lower = value.lower()
		matches = [
			i + 1 for i, name in enumerate(Months.all_english()) if name.startswith(value_lower)
		]

		if len(matches) == 1:
			return matches[0]
		elif len(matches) > 1:
			matched_names = [Months.all_english()[m - 1] for m in matches]
			self.fail(f"Ambiguous month '{value}' - matches: {matched_names}", param, ctx)
		else:
			self.fail(f"Unknown month '{value}'", param, ctx)

	def shell_complete(
		self,
		ctx: click.Context,
		param: click.Parameter,
		incomplete: str,
	) -> list[CompletionItem]:
		"""Provide shell autocompletion."""

		incomplete_lower = incomplete.lower()
		return [
			CompletionItem(name)
			for name in Months.all_english()
			if name.startswith(incomplete_lower) or incomplete == ''
		]


MONTH = MonthType()


@click.group(invoke_without_command=True, context_settings={'help_option_names': ['-h', '--help']})
@click.option('--version', '-v', is_flag=True, help='Show version and exit.')
@click.option('--config', '-c', type=click.Path(exists=True), help='Config file path.')
@click.option('--verbose', is_flag=True, help='Enable verbose/debug logging.')
@click.pass_context
def main(ctx: click.Context, version: bool, config: Optional[str], verbose: bool) -> None:
	"""🕐 Hilan Attendance Auto-Fill CLI

	Smart tool to automatically fill your attendance hours on Hilan.

	\b
	Quick start:
		1. Run 'hilan init' to create your config
		2. Run 'hilan status' to view current attendance
		3. Run 'hilan fill' to fill missing days

	\b
	Config file: ~/.config/hilan-attendance.json

	\b
	Use -c to specify a custom config file:
		hilan -c ./my-config.json status
	"""
	if verbose:
		enable_debug_logging()
	ctx.ensure_object(dict)
	ctx.obj['config_path'] = Path(config) if config else None

	if version:
		logger.info('hilan-attendance version %s', __version__)
		return

	if ctx.invoked_subcommand is None:
		click.echo(ctx.get_help())


def _install_shell_completions() -> list[tuple[str, str]]:
	"""Install shell completions for bash, fish, and zsh."""
	home = Path.home()
	completions_installed: list[tuple[str, str]] = []

	# Bash completion
	bash_completion_dir = home / '.bash_completion.d'
	bash_completion_dir.mkdir(exist_ok=True)
	bash_file = bash_completion_dir / 'hilan.bash'
	try:
		result = subprocess.run(
			['hilan'],
			env={**os.environ, '_HILAN_COMPLETE': 'bash_source'},
			capture_output=True,
			text=True,
			check=False,
		)
		if result.stdout:
			bash_file.write_text(result.stdout)
			completions_installed.append(('bash', str(bash_file)))
	except (subprocess.SubprocessError, OSError):
		pass

	# Fish completion
	fish_completion_dir = home / '.config' / 'fish' / 'completions'
	if fish_completion_dir.parent.exists():
		fish_completion_dir.mkdir(exist_ok=True)
		fish_file = fish_completion_dir / 'hilan.fish'
		try:
			result = subprocess.run(
				['hilan'],
				env={**os.environ, '_HILAN_COMPLETE': 'fish_source'},
				capture_output=True,
				text=True,
				check=False,
			)
			if result.stdout:
				fish_file.write_text(result.stdout)
				completions_installed.append(('fish', str(fish_file)))
		except (subprocess.SubprocessError, OSError):
			pass

	# Zsh completion
	zsh_completion_dir = home / '.zfunc'
	zsh_completion_dir.mkdir(exist_ok=True)
	zsh_file = zsh_completion_dir / '_hilan'
	try:
		result = subprocess.run(
			['hilan'],
			env={**os.environ, '_HILAN_COMPLETE': 'zsh_source'},
			capture_output=True,
			text=True,
			check=False,
		)
		if result.stdout:
			zsh_file.write_text(result.stdout)
			completions_installed.append(('zsh', str(zsh_file)))
	except (subprocess.SubprocessError, OSError):
		pass

	return completions_installed


@main.command(context_settings={'help_option_names': ['-h', '--help']})
@click.option('--force', '-f', is_flag=True, help='Overwrite existing config.')
@click.option('--skip-completions', is_flag=True, help='Skip shell completion setup.')
def init(force: bool, skip_completions: bool) -> None:
	"""Initialize configuration and install browser.

	Creates a configuration file at ~/.config/hilan-attendance.json,
	installs the Playwright browser, and sets up shell completions.
	"""
	config_path = get_config_path()

	if config_exists() and not force:
		logger.warning('Configuration already exists at %s', config_path)
		logger.info('Use --force to overwrite.')
		return

	config = create_config_interactive()
	save_config(config)

	# Install browser
	logger.info('Installing Playwright browser...')
	try:
		result = subprocess.run(
			['playwright', 'install', 'chromium'], capture_output=True, text=True, check=False
		)
		if result.returncode == 0:
			logger.success('✓ Browser installed!')
		else:
			logger.warning("Browser install failed. Run 'playwright install chromium' manually.")
	except (subprocess.SubprocessError, OSError) as e:
		logger.warning('Could not install browser: %s', e)
		logger.warning("Run 'playwright install chromium' manually.")

	# Install shell completions
	completion_info = ''
	if not skip_completions:
		logger.info('Setting up shell completions...')
		completions = _install_shell_completions()
		if completions:
			for shell, path in completions:
				logger.success('✓ %s: %s', shell, path)

			# Add setup hints
			hints = []
			shells_installed = [c[0] for c in completions]
			if 'bash' in shells_installed:
				hints.append('  bash: Add to ~/.bashrc: source ~/.bash_completion.d/hilan.bash')
			if 'zsh' in shells_installed:
				hints.append(
					'  zsh:  Add to ~/.zshrc: fpath+=~/.zfunc; autoload -Uz compinit && compinit'
				)
			if 'fish' in shells_installed:
				hints.append('  fish: Completions auto-loaded ✓')

			if hints:
				completion_info = '\n\nShell completions:\n' + '\n'.join(hints)
		else:
			logger.warning('Could not install completions')

	console.print(
		Panel(
			f'[green]✓ Setup complete![/green]\n\n'
			f'Config: [cyan]{config_path}[/cyan]'
			f'{completion_info}\n\n'
			f"[dim]Run 'hilan status' to view attendance.[/dim]",
			title='🎉 Ready',
			border_style='green',
		)
	)


@main.command(context_settings={'help_option_names': ['-h', '--help']})
@click.option('--month', '-m', type=MONTH, help='Month (1-12 or name). Default: current.')
@click.option('--year', '-y', type=int, help='Year. Default: current.')
@click.option('--dry-run', '-d', is_flag=True, help='Preview without submitting.')
@click.option('--today', '-t', is_flag=True, help='Only fill today (if needed).')
@click.option('--up-to-today', '-u', is_flag=True, help='Fill all days up to and including today.')
@click.pass_context
def fill(
	ctx: click.Context,
	month: Optional[int],
	year: Optional[int],
	dry_run: bool,
	today: bool,
	up_to_today: bool,
) -> None:
	"""Fill attendance for a month.

	\b
	Examples:
		hilan fill                    # Fill current month
		hilan fill -m 11 -y 2024      # Fill November 2024
		hilan fill --dry-run          # Preview changes
		hilan fill --today            # Only fill today if needed
		hilan fill --up-to-today      # Fill all days up to today
	"""
	config_path = ctx.obj.get('config_path')
	try:
		cfg = load_config(config_path)
	except (FileNotFoundError, ValueError) as e:
		logger.error('%s', e)
		return

	# Determine pay period - use current pay period if not specified
	if month is None and year is None:
		fill_year, fill_month = cfg.pay_period
	else:
		today_date = date.today()
		fill_year = year or today_date.year
		fill_month = month or today_date.month

	run_attendance_flow(
		config=cfg,
		year=fill_year,
		month=fill_month,
		dry_run=dry_run,
		today_only=today,
		up_to_today=up_to_today,
	)


@main.command(context_settings={'help_option_names': ['-h', '--help']})
@click.option('--month', '-m', type=MONTH, help='Month (1-12 or name). Default: current.')
@click.option('--year', '-y', type=int, help='Year. Default: current.')
@click.pass_context
def status(ctx: click.Context, month: Optional[int], year: Optional[int]) -> None:
	"""View current attendance status.

	Shows a summary of your attendance for the month.
	"""
	config_path = ctx.obj.get('config_path')
	try:
		cfg = load_config(config_path)
	except (FileNotFoundError, ValueError) as e:
		logger.error('%s', e)
		return

	# Determine pay period - use current pay period if not specified
	if month is None and year is None:
		view_year, view_month = cfg.pay_period
	else:
		today_date = date.today()
		view_year = year or today_date.year
		view_month = month or today_date.month

	logger.info('Checking attendance for %d/%d...', view_month, view_year)

	with HilanBrowser(cfg) as browser:
		attendance = fetch_attendance_data(browser, view_year, view_month)
		if attendance is None:
			return
		display_current_status(attendance, cfg.pattern)

		# Summary stats
		work_day_records = [
			r for r in attendance.records if r.date.weekday() in cfg.pattern.work_days
		]
		complete = len([r for r in work_day_records if r.is_complete])
		empty = len([r for r in work_day_records if r.needs_filling])
		partial = len(
			[r for r in work_day_records if r.has_existing_entry and not r.has_existing_exit]
		)

		logger.info('Summary:')
		logger.success('  ✓ Filled: %d', complete)
		if partial > 0:
			logger.info('  ⚡ Partial: %d', partial)
		logger.info('  ✗ Empty: %d', empty)

		if not cfg.headless:
			input('\nPress Enter to close browser...')


if __name__ == '__main__':
	main()
