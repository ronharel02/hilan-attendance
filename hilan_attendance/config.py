"""Configuration management for Hilan Attendance CLI."""

from datetime import time as dt_time
from pathlib import Path
from typing import Optional

from pydantic import HttpUrl, SecretStr, TypeAdapter, ValidationError
from rich.prompt import Confirm, Prompt

from . import logger
from .models import AttendancePattern, Config, WorkType
from .vocabulary import Weekdays

DEFAULT_CONFIG_PATH = Path.home() / '.config' / 'hilan-attendance.json'


def get_config_path() -> Path:
	"""Get the configuration file path."""
	return DEFAULT_CONFIG_PATH


def config_exists() -> bool:
	"""Check if the configuration file exists."""
	return get_config_path().exists()


def load_config(path: Optional[Path] = None) -> Config:
	"""Load configuration from JSON file."""
	config_path = path or get_config_path()

	if not config_path.exists():
		raise FileNotFoundError(
			f"Config not found at {config_path}\nRun 'hilan init' to create one."
		)

	try:
		return Config.model_validate_json(config_path.read_text(encoding='utf-8'))
	except ValidationError as e:
		raise ValueError(f'Invalid config: {e}') from e


def save_config(config: Config, path: Optional[Path] = None) -> None:
	"""Save configuration to JSON file."""
	config_path = path or get_config_path()
	config_path.parent.mkdir(parents=True, exist_ok=True)

	try:
		config_path.write_text(config.model_dump_json(indent=2), encoding='utf-8')
		config_path.chmod(0o600)
	except OSError as e:
		raise OSError(f'Failed to save config to {config_path}: {e}') from e


def create_config_interactive() -> Config:
	"""Create a new configuration interactively."""

	time_adapter = TypeAdapter(dt_time)

	def _prompt_time(label: str, default: dt_time) -> dt_time:
		"""Prompt for a time value with Pydantic validation."""
		default_str = default.strftime('%H:%M')
		while True:
			value = Prompt.ask(f'[yellow]{label} (HH:MM)[/yellow]', default=default_str)
			try:
				return time_adapter.validate_python(value)
			except ValidationError:
				logger.error('Invalid time format. Please use HH:MM (e.g., 09:00)')

	logger.info('🔧 Hilan Attendance Setup\n')

	# Base URL
	logger.info('Hilan URL:')
	base_url = Prompt.ask(
		'[yellow]Hilan base URL[/yellow]', default='https://yourcompany.hilan.co.il'
	)
	# Strip trailing slash if present
	base_url = base_url.rstrip('/')

	# Credentials
	logger.info('\nCredentials:')
	username = Prompt.ask('[yellow]Username[/yellow]')
	password = SecretStr(Prompt.ask('[yellow]Password[/yellow]', password=True))

	# Times
	logger.info('\nDefault Times:')
	entry_time = _prompt_time('Entry time', default=dt_time(9, 0))
	exit_time = _prompt_time('Exit time', default=dt_time(18, 0))

	# Work days with per-day work type
	logger.info('\nWork Days:')
	logger.info('For each day, enter: office, home, abroad, meeting, or skip\n')

	# Default work days (Israeli work week: Sunday-Thursday)
	default_work_days = {
		Weekdays.SUNDAY,
		Weekdays.MONDAY,
		Weekdays.TUESDAY,
		Weekdays.WEDNESDAY,
		Weekdays.THURSDAY,
	}

	days = {}
	for day in Weekdays._members():
		default_type = WorkType.OFFICE if day in default_work_days else WorkType.SKIP
		response = Prompt.ask(
			f'[yellow]{day.value.capitalize()}[/yellow]', default=default_type.value
		)

		try:
			work_type = WorkType(response.lower())
		except ValueError:
			work_type = WorkType.SKIP if response.lower() == 'skip' else WorkType.OFFICE

		if work_type != WorkType.SKIP:
			days[day.value] = work_type

	# Pay period start day
	logger.info('\nPay Period:')
	pay_period_str = Prompt.ask('[yellow]Pay period start day (1-28)[/yellow]', default='20')
	try:
		pay_period_start_day = int(pay_period_str)
		if not 1 <= pay_period_start_day <= 28:
			logger.warning('Invalid day, using default (20)')
			pay_period_start_day = 20
	except ValueError:
		logger.warning('Invalid day, using default (20)')
		pay_period_start_day = 20

	# Headless
	headless = Confirm.ask('\n[yellow]Run browser in headless mode?[/yellow]', default=False)

	pattern = AttendancePattern(entry_time=entry_time, exit_time=exit_time, days=days)

	return Config(
		username=username,
		password=password,
		url=HttpUrl(base_url),
		pattern=pattern,
		headless=headless,
		pay_period_start_day=pay_period_start_day,
	)
