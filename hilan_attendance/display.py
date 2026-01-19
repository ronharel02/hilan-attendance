"""Display and formatting utilities for attendance data."""

from datetime import date
from typing import Optional

from rich.table import Table

from . import console, logger
from .models import AttendancePattern, AttendanceRecord, MonthAttendance, WorkType
from .vocabulary import DayTypes, Weekdays


def translate_note(note: str) -> str:
	"""Translate Hebrew day type notes to English."""
	if not note:
		return ''
	return DayTypes.to_english(note)


def get_work_type_label(work_type: Optional[WorkType], default: str = 'Work') -> str:
	"""Get the display label for a work type."""
	return work_type.label if work_type else default


def format_record_current_state(record: AttendanceRecord) -> str:
	"""Format the current state of an attendance record for display.

	Returns a rich-formatted string showing the current entry/exit times and work type.
	"""
	if record.is_complete and record.entry_time and record.exit_time:
		type_label = get_work_type_label(record.work_type)
		times = f'{record.entry_time.strftime("%H:%M")}-{record.exit_time.strftime("%H:%M")}'
		return f'[green]{type_label} ({times})[/green]'
	elif record.has_existing_entry and record.entry_time:
		type_label = get_work_type_label(record.work_type)
		exit_str = record.exit_time.strftime('%H:%M') if record.exit_time else '?'
		times = f'{record.entry_time.strftime("%H:%M")}-{exit_str}'
		return f'[yellow]{type_label} ({times})[/yellow]'
	elif record.note:
		return f'[yellow]{translate_note(record.note)}[/yellow]'
	else:
		return '[dim]-[/dim]'


def display_current_status(attendance: MonthAttendance, pattern: AttendancePattern) -> None:
	"""Display current attendance status as a Rich table."""
	if not attendance.records:
		logger.warning('No records found.')
		return

	sorted_records = sorted(attendance.records, key=lambda r: r.date)
	start = sorted_records[0].date
	end = sorted_records[-1].date

	table = Table(
		title=f'📅 Attendance ({start.strftime("%d/%m")} - {end.strftime("%d/%m/%Y")})',
		show_header=True,
		header_style='bold cyan',
	)

	table.add_column('Date', style='dim')
	table.add_column('Day', style='dim')
	table.add_column('Current', justify='center')
	table.add_column('Status', justify='center')

	for record in sorted_records:
		day = Weekdays.from_number(record.date.weekday())
		assert day is not None, f'Invalid weekday {record.date.weekday()} for date {record.date}'
		day_name = day.short
		date_str = record.date.strftime('%d/%m')
		is_work_day = record.date.weekday() in pattern.work_days

		# Current display
		current = format_record_current_state(record)

		# Status
		if record.is_complete:
			status = '[green]✓ Filled[/green]'
		elif record.has_existing_entry and not record.has_existing_exit:
			status = '[yellow]⚡ Partial[/yellow]'
		elif record.note:
			status = f'[yellow]📋 {translate_note(record.note)}[/yellow]'
		elif not is_work_day:
			status = '[dim]Weekend[/dim]'
		else:
			status = '[red]✗ Empty[/red]'

		table.add_row(date_str, day_name, current, status, style='dim' if not is_work_day else None)

	console.print(table)


def display_fill_plan(
	attendance: MonthAttendance,
	pattern: AttendancePattern,
	up_to_date: Optional[date] = None,
	single_date: Optional[date] = None,
) -> None:
	"""Display the fill plan as a Rich table.

	Args:
		attendance: The attendance data for the month.
		pattern: The attendance pattern configuration.
		up_to_date: If provided, only show records up to this date.
		single_date: If provided, only show this specific date.
	"""
	if not attendance.records:
		return

	sorted_records = sorted(attendance.records, key=lambda r: r.date)

	# Filter to single_date if specified (takes precedence)
	if single_date:
		sorted_records = [r for r in sorted_records if r.date == single_date]
	elif up_to_date:
		sorted_records = [r for r in sorted_records if r.date <= up_to_date]

	if not sorted_records:
		return

	start = sorted_records[0].date
	end = sorted_records[-1].date

	# Use simpler title for single date
	if single_date or start == end:
		title = f'📋 Fill Plan ({start.strftime("%d/%m/%Y")})'
	else:
		title = f'📋 Fill Plan ({start.strftime("%d/%m")} - {end.strftime("%d/%m/%Y")})'

	table = Table(
		title=title,
		show_header=True,
		header_style='bold cyan',
	)

	table.add_column('Date', style='dim')
	table.add_column('Day', style='dim')
	table.add_column('Current', justify='center')
	table.add_column('Action', justify='center')

	for record in sorted_records:
		day = Weekdays.from_number(record.date.weekday())
		assert day is not None, f'Invalid weekday {record.date.weekday()} for date {record.date}'
		day_name = day.short
		date_str = record.date.strftime('%d/%m')
		is_work_day = record.date.weekday() in pattern.work_days

		# Get work type for this day
		day_work_type = pattern.get_work_type(record.date.weekday())
		day_type_label = get_work_type_label(day_work_type, default='Office')

		# Current state
		current = format_record_current_state(record)

		# Action
		if record.is_complete:
			action = '[dim]Skip (filled)[/dim]'
			row_style = 'dim'
		elif record.note:
			action = f'[dim]Skip ({translate_note(record.note)})[/dim]'
			row_style = 'dim'
		elif not is_work_day:
			action = '[dim]Skip (weekend)[/dim]'
			row_style = 'dim'
		elif record.has_existing_entry and not record.has_existing_exit:
			action = f'[cyan]→ Add exit: {pattern.exit_time.strftime("%H:%M")}[/cyan]'
			row_style = None
		elif record.is_empty or not record.has_existing_entry:
			times = f'{pattern.entry_time.strftime("%H:%M")}-{pattern.exit_time.strftime("%H:%M")}'
			action = f'[green]→ {day_type_label} ({times})[/green]'
			row_style = 'bold'
		else:
			action = '[dim]Review manually[/dim]'
			row_style = None

		table.add_row(date_str, day_name, current, action, style=row_style)

	console.print(table)
