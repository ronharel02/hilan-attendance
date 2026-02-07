"""Attendance filling logic."""

from datetime import date
from typing import Optional

from rich.prompt import Confirm

from . import logger
from .browser import HilanBrowser
from .display import display_fill_plan, translate_note
from .models import AttendancePattern, Config, MonthAttendance, WorkType


def fill_attendance(
	browser: HilanBrowser,
	attendance: MonthAttendance,
	pattern: AttendancePattern,
	dry_run: bool = False,
	only_dates: Optional[list[date]] = None,
) -> tuple[int, int]:
	"""Fill attendance for empty work days.

	Args:
		browser: HilanBrowser instance to use for filling.
		attendance: The attendance data for the month.
		pattern: The attendance pattern configuration.
		dry_run: If True, don't actually fill anything.
		only_dates: If provided, only fill these specific dates.

	Returns:
		Tuple of (successful_count, failed_count).
	"""
	logger.info('🚀 Filling attendance...')

	# Collect all records that need to be filled
	records_to_fill = []

	for record in attendance.records:
		# If only_dates specified, skip other dates
		if only_dates and record.date not in only_dates:
			continue

		# Skip non-work days
		if record.date.weekday() not in pattern.work_days:
			continue

		# Skip already complete
		if record.is_complete:
			continue

		# Skip days with special status (sick, vacation, etc.)
		if record.note:
			logger.debug('⏭ %s (%s)', record.date.strftime('%d/%m'), translate_note(record.note))
			continue

		# Add to batch
		records_to_fill.append((
			record.date,
			record.entry_time if record.has_existing_entry else pattern.entry_time,
			record.exit_time if record.has_existing_exit else pattern.exit_time,
			pattern.get_work_type(record.date.weekday()) or WorkType.OFFICE
		))

	# Fill all records in one efficient batch operation
	if records_to_fill:
		successful, failed = browser.fill_batch_attendance(records_to_fill, dry_run=dry_run)
	else:
		logger.debug('No records to fill')
		successful = 0
		failed = 0

	return successful, failed


def fetch_attendance_data(
	browser: HilanBrowser, year: int, month: int
) -> Optional[MonthAttendance]:
	"""Login, navigate to attendance page, and fetch data.

	Args:
		browser: HilanBrowser instance (already created).
		year: Year to fetch.
		month: Month to fetch.

	Returns:
		MonthAttendance or None on error.
	"""
	if not browser.login():
		logger.error('Login failed.')
		return None

	browser.navigate_to_attendance()
	return browser.get_attendance(year, month)


def run_attendance_flow(
	config: Config,
	year: int,
	month: int,
	dry_run: bool = False,
	today_only: bool = False,
	up_to_today: bool = False,
) -> None:
	"""Run the full attendance filling flow.

	Args:
		config: Application configuration.
		year: Year to fill.
		month: Month to fill.
		dry_run: If True, don't actually fill anything.
		today_only: If True, only fill today.
		up_to_today: If True, fill all days up to and including today.
	"""
	today_date = date.today()

	if today_only:
		logger.info('Filling today (%s)...', today_date.strftime('%d/%m/%Y'))
	elif up_to_today:
		logger.info('Filling up to today (%s)...', today_date.strftime('%d/%m/%Y'))
	else:
		logger.info('╔══════════════════════════════════════════╗')
		logger.info('║      Hilan Attendance Auto-Fill          ║')
		logger.info('╚══════════════════════════════════════════╝')

	if dry_run:
		logger.warning('DRY RUN MODE - No changes will be made')

	with HilanBrowser(config) as browser:
		attendance = fetch_attendance_data(browser, year, month)
		if attendance is None:
			return

		# Determine date filter for display
		if today_only:
			display_up_to = today_date  # Will show just today
		elif up_to_today:
			display_up_to = today_date  # Will show up to today
		else:
			display_up_to = None  # Show all

		display_fill_plan(
			attendance,
			config.pattern,
			up_to_date=display_up_to,
			single_date=today_date if today_only else None,
		)

		# Filter days to fill
		to_fill = [
			r
			for r in attendance.records
			if r.date.weekday() in config.pattern.work_days and not r.is_complete and not r.note
		]

		# If up_to_today, filter to days <= today
		if up_to_today:
			to_fill = [r for r in to_fill if r.date <= today_date]

		# If today_only, filter to just today
		if today_only:
			to_fill = [r for r in to_fill if r.date == today_date]

			if not to_fill:
				# Check why
				today_record = next((r for r in attendance.records if r.date == today_date), None)
				if today_record is None:
					logger.warning(
						'Today (%s) is not in current pay period', today_date.strftime('%d/%m/%Y')
					)
				elif today_date.weekday() not in config.pattern.work_days:
					logger.success('✓ Today is not a work day in your pattern')
				elif today_record.is_complete:
					logger.success('✓ Today is already filled')
				elif today_record.note:
					logger.success('✓ Today has a note: %s', today_record.note)
				else:
					logger.success('✓ Nothing to fill for today')
				return

		if not to_fill:
			logger.success('✓ Nothing to fill!')
			if not config.headless:
				input('\nPress Enter to close browser...')
			return

		if dry_run:
			if today_only:
				logger.warning('DRY RUN: Would fill today')
			else:
				logger.warning('DRY RUN: Would fill %d days', len(to_fill))
			if not config.headless:
				input('\nPress Enter to close browser...')
			return

		# Confirm (skip for today_only since it's just one day)
		if not today_only and not Confirm.ask(
			f'\n[yellow]Fill {len(to_fill)} days?[/yellow]', default=True
		):
			logger.info('Cancelled.')
			return

		successful, failed = fill_attendance(
			browser,
			attendance,
			config.pattern,
			dry_run,
			only_dates=[r.date for r in to_fill],
		)

		logger.info('=' * 40)
		logger.success('✓ Filled: %d', successful)
		if failed > 0:
			logger.error('✗ Failed: %d', failed)
		logger.info('=' * 40)

		if not config.headless:
			input('Press Enter to close browser...')
