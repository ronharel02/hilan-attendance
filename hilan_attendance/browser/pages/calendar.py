"""Calendar/attendance page automation for Hilan."""

import calendar as cal
import re
from datetime import date, time
from enum import IntEnum
from typing import Optional

from playwright.sync_api import Locator

from ... import logger
from ...models import AttendanceRecord, MonthAttendance, WorkType
from ...vocabulary import AriaLabels, Buttons, Months, StatusNotes
from .base import BasePage


def parse_time_string(time_str: str) -> Optional[time]:
	"""Parse a time string in HH:MM format to a time object."""
	if not time_str:
		return None
	if match := re.compile(r'^(\d{1,2}):(\d{2})$').match(time_str.strip()):
		return time(int(match.group(1)), int(match.group(2)))
	return None


def get_cell_date(
	day: int, target_month: int, target_year: int, start_day: int
) -> tuple[int, int, int]:
	"""Determine the actual date for a calendar cell in Hilan's pay period view.

	Hilan shows cross-month periods, so days >= start_day belong to the previous month.

	Args:
		day: Day number from the calendar cell.
		target_month: The pay period's target month (1-12).
		target_year: The pay period's target year.
		start_day: Day of month when pay period starts.

	Returns:
		Tuple of (year, month, day) for the actual date.
	"""
	if day >= start_day:
		# This day belongs to previous month
		if target_month == 1:
			return target_year - 1, 12, day
		return target_year, target_month - 1, day
	return target_year, target_month, day


class Selector:
	"""CSS selectors for calendar/attendance page elements."""

	MONTH_DROPDOWN = 'ctl00_mp_calendar_monthChanged'
	ENTRY_INPUT = f'input[aria-label*="{AriaLabels.ENTRY}"]'
	EXIT_INPUT = f'input[aria-label*="{AriaLabels.EXIT}"]'
	WORK_TYPE_SELECT = f'select[aria-label*="{AriaLabels.REPORT_TYPE}"]'
	SAVE_BUTTON = 'input[id*="btnSave"]'
	FILLED_DAY_CLASS = 'cDIES'


class Timing(IntEnum):
	"""Timing constants (milliseconds)"""

	WAIT_AFTER_CLICK = 300
	WAIT_AFTER_CLEAR = 200
	WAIT_AFTER_FILL = 100
	WAIT_FOR_TABLE_LOAD = 500
	WAIT_AFTER_SAVE = 500
	WAIT_FOR_DROPDOWN = 300
	WAIT_FOR_DROPDOWN_OPEN = 100


class CalendarPage(BasePage):
	"""Handles Hilan calendar/attendance page interactions.

	IMPORTANT: How the Hilan UI works (discovered via HTML analysis):

	1. Calendar View: Shows all days in the month with existing entry times
		- Each day cell has: class="cDIES", days="9455" (unique ID), aria-label="20"
		- The 'title' attribute shows existing entry time (e.g., title="9:00")
		- Clicking a day cell executes: onclick="_dSD(this,9455)"

	2. Detail Form (Single Row): Shows input fields for ONE selected day at a time
		- Only ONE set of inputs is visible at any time (not all days at once!)
		- The form shows: ReportDate, entry input, exit input, work type select
		- Row ID format: EmployeeReports_row_0_0 (always row 0)

	3. Workflow:
		a) Click a day in calendar -> loads that day's data into the detail form
		b) OR click multiple days -> click "Selected Days" button -> loads all
		c) Fill the visible inputs in the detail form
		d) Click "Save" button to submit

	4. Stable Selectors (aria-label attributes in Hebrew):
		- Entry input: aria-label="כניסה ריק" (Entry empty) or "כניסה" prefix
		- Exit input: aria-label="יציאה ריק" (Exit empty) or "יציאה" prefix
		- Work type: aria-label="סוג דיווח ריק" (Report type empty)
		These are MUCH more stable than dynamic IDs.
	"""

	PATH = '/Hilannetv2/Attendance/calendarpage.aspx'

	def navigate_to_month(self, year: int, month: int) -> bool:
		"""Navigate to a specific month in the Hilan calendar.

		Hilan uses a custom dropdown with <li> elements that have onclick handlers.
		The itemvalue format is DD/MM/YYYY where DD is pay period start day.

		Args:
			year: Target year.
			month: Target month (1-12).

		Returns:
			True if navigation was successful.
		"""
		target_month_name = Months.from_number(month)
		if not target_month_name:
			logger.error('Invalid month: %s', month)
			return False

		# First check current month
		current_info = self.page.evaluate(f"""
			() => {{
				const span = document.querySelector('#{Selector.MONTH_DROPDOWN}');
				if (span) {{
					const text = span.innerText.trim();
					const match = text.match(/({'|'.join(Months.all_hebrew())})\\s+(\\d{{4}})/);
					if (match) {{
						return {{ month: match[1], year: parseInt(match[2]) }};
					}}
				}}
				return null;
			}}
		""")

		if current_info:
			current_month_num = Months.to_number(current_info['month'])
			if current_month_num == month and current_info['year'] == year:
				return True  # Already on correct month

		# Hilan's itemvalue format: pay period starts on configured day of PREVIOUS month
		# So November 2025 (נובמבר 2025) has itemvalue="20/10/2025" (if pay_period_start_day=20)
		pay_period_day = self.config.pay_period_start_day
		prev_month = month - 1 if month > 1 else 12
		prev_year = year if month > 1 else year - 1
		target_itemvalue = f'{pay_period_day}/{prev_month:02d}/{prev_year}'

		logger.debug('Navigating to %s %d...', target_month_name, year)

		try:
			# Step 1: Click on the month dropdown SPAN to open it
			# Note: There are 2 elements with this ID - span and ul
			dropdown_trigger = self.page.locator(f'span#{Selector.MONTH_DROPDOWN}')
			if dropdown_trigger.count() == 0:
				# Try without span prefix
				dropdown_trigger = self.page.locator(f'#{Selector.MONTH_DROPDOWN}')
				if dropdown_trigger.count() == 0:
					logger.warning('Month selector span not found')
					return False

			dropdown_trigger.first.click()
			self.page.wait_for_timeout(Timing.WAIT_FOR_DROPDOWN)

			# Step 2: Make dropdown visible (it starts with display:none)
			self.page.evaluate("""
				() => {
					const dropdown = document.querySelector('.BulletedList');
					if (dropdown) {
						dropdown.style.display = 'block';
					}
				}
			""")
			self.page.wait_for_timeout(Timing.WAIT_FOR_DROPDOWN_OPEN)

			# Step 3: Click on the target month using Playwright locator
			target_item = self.page.locator(f'li[itemvalue="{target_itemvalue}"]')

			if target_item.count() > 0:
				target_item.click()
				self.page.wait_for_timeout(Timing.WAIT_FOR_TABLE_LOAD)
				self.wait_for_load()
				logger.success('✓ Navigated to %s %d', target_month_name, year)
				return True

			# Fallback: try clicking by text content
			target_text = f'{target_month_name} {year}'
			text_item = self.page.locator(f'li:has-text("{target_text}")')

			if text_item.count() > 0:
				text_item.first.click()
				self.page.wait_for_timeout(Timing.WAIT_FOR_TABLE_LOAD)
				self.wait_for_load()
				logger.success('✓ Navigated to %s %d', target_month_name, year)
				return True

			# Debug: show available options
			available = self.page.evaluate("""
				() => Array.from(document.querySelectorAll('li[itemvalue]'))
					.map(li => ({ value: li.getAttribute('itemvalue'), text: li.innerText.trim() }))
			""")
			logger.warning('Target month not found. Looking for itemvalue=%s', target_itemvalue)
			if available:
				logger.debug(
					'Available: %s...', [m['value'] + '=' + m['text'] for m in available[:5]]
				)
			return False

		except Exception as e:
			logger.warning('Navigation error: %s', e)
			return False

	def get_attendance(self, year: int, month: int) -> Optional[MonthAttendance]:
		"""Get attendance with full entry/exit times and work types.

		Uses fast JavaScript to click all filled days, then parses the detail table.

		Args:
			year: Year to read.
			month: Month to read (1-12).

		Returns:
			MonthAttendance with all records for the month, or None if navigation failed.
		"""
		# Navigate to the correct month first
		if not self.navigate_to_month(year, month):
			logger.error('Could not navigate to %d/%d', month, year)
			return None

		logger.info('📅 Reading attendance...')

		# Get basic records from calendar
		records = self._parse_calendar(year, month)

		if not records:
			logger.warning('No days found in calendar')
			return MonthAttendance(year=year, month=month, records=[])

		filled_days = [r for r in records if r.has_existing_entry]
		logger.debug('Selecting %d filled days...', len(filled_days))

		# Click all filled days instantly with JavaScript
		self.page.evaluate(
			f"() => document.querySelectorAll('td.{Selector.FILLED_DAY_CLASS}').forEach(c => c.click())"
		)

		# Click "ימים נבחרים" to load detail table
		btn = self.page.locator(f'text={Buttons.SELECTED_DAYS}')
		if btn.count() > 0:
			btn.first.click()
			self.page.wait_for_timeout(Timing.WAIT_FOR_TABLE_LOAD)
			self.wait_for_load()
		else:
			logger.warning('Could not find detail table button')
			return MonthAttendance(year=year, month=month, records=records)

		# Extract data from detail table with JavaScript
		# Note: Hilan has TWO sets of entry/exit inputs per row:
		#   1. "דיווחי שעון" (Clock reports) - actual punch times, often empty
		#   2. "דיווחי עובד" (Employee reports) - manually entered times
		# We need to find the inputs with actual values, not the empty clock ones.
		detail_data = self.page.evaluate(f"""
			() => {{
				const rows = document.querySelectorAll('tr[id*="_row_"]');

				// Helper to find input with a valid time value from multiple matches
				const findValidTimeInput = (inputs) => {{
					for (const input of inputs) {{
						const val = input?.value?.trim();
						// Skip empty, placeholder, or clock-style empty values
						if (val && val !== '' && val !== '--:--' && /^\\d{{1,2}}:\\d{{2}}$/.test(val)) {{
							return input;
						}}
					}}
					// Fallback: return last input (usually the employee reports one)
					return inputs[inputs.length - 1] || null;
				}};

				return Array.from(rows).map(row => {{
					const dateCell = row.querySelector('td[id*="ReportDate"]');
					if (!dateCell) return null;

					const dateMatch = dateCell.innerText.trim().match(/(\\d{{1,2}})\\/(\\d{{1,2}})/);
					if (!dateMatch) return null;

					// Get ALL matching inputs, then find the one with a valid value
					const entryInputs = row.querySelectorAll('{Selector.ENTRY_INPUT}');
					const exitInputs = row.querySelectorAll('{Selector.EXIT_INPUT}');
					const workTypeSelect = row.querySelector('{Selector.WORK_TYPE_SELECT}');

					const entryInput = findValidTimeInput(entryInputs);
					const exitInput = findValidTimeInput(exitInputs);

					return {{
						day: parseInt(dateMatch[1]),
						month: parseInt(dateMatch[2]),
						entry: entryInput?.value || '',
						exit: exitInput?.value || '',
						workTypeCode: workTypeSelect?.value || ''
					}};
				}}).filter(Boolean);
			}}
		""")

		# Map records by (day, month) for fast lookup
		record_map = {(r.date.day, r.date.month): r for r in records}

		logger.debug('Found %d rows in detail table...', len(detail_data))

		# Update records with detail data
		for data in detail_data:
			if not (record := record_map.get((data['day'], data['month']))):
				continue

			if data.get('entry') and (parsed_entry := parse_time_string(data['entry'])):
				record.entry_time = parsed_entry

			if data.get('exit') and (parsed_exit := parse_time_string(data['exit'])):
				record.exit_time = parsed_exit

			if data.get('workTypeCode'):
				record.work_type = WorkType.from_hilan_code(data['workTypeCode'])

		records.sort(key=lambda r: r.date)
		if records:
			logger.info(
				'✓ Parsed %d days (%s - %s)',
				len(records),
				records[0].date.strftime('%d/%m'),
				records[-1].date.strftime('%d/%m'),
			)

		return MonthAttendance(year=year, month=month, records=records)

	def fill_batch(
		self,
		records_to_fill: list[tuple[date, time, time, WorkType]],
		dry_run: bool = False,
	) -> tuple[int, int]:
		"""Fill attendance for multiple days in one batch operation.

		This is MUCH more efficient than filling one day at a time!
		Instead of: clear -> click day -> select -> fill -> save (repeated for each day)
		We do: clear -> click ALL days -> select once -> fill all -> save once

		Args:
			records_to_fill: List of (date, entry_time, exit_time, work_type) tuples.
			dry_run: If True, show what would be done without actually doing it.

		Returns:
			Tuple of (successful_count, failed_count).
		"""
		if not records_to_fill:
			return 0, 0

		logger.info('📦 Batch filling %d days...', len(records_to_fill))

		if dry_run:
			for record_date, entry_time, exit_time, work_type in records_to_fill:
				day_str = record_date.strftime('%d/%m/%Y')
				work_label = work_type.label
				logger.info(
					'📝 %s: %s (%s-%s) (dry run)',
					day_str,
					work_label,
					entry_time.strftime('%H:%M'),
					exit_time.strftime('%H:%M'),
				)
			return len(records_to_fill), 0

		try:
			# Step 1: Click Clear button to deselect all days
			logger.debug('🧹 Clearing selection...')
			clear_btn = self.page.locator(f'input[value="{Buttons.CLEAR}"]')
			if clear_btn.count() > 0 and clear_btn.is_visible():
				clear_btn.first.click()
				self.page.wait_for_timeout(Timing.WAIT_AFTER_CLEAR)

			# Step 2: Click all days in the calendar
			logger.debug('🖱️  Selecting %d days...', len(records_to_fill))
			day_numbers = [record_date.day for record_date, _, _, _ in records_to_fill]

			clicked = self.page.evaluate(
				f"""
				(dayNumbers) => {{
					const clickedDays = [];
					const failedDays = [];

					for (const dayNum of dayNumbers) {{
						// Find day cell by aria-label
						const cells = document.querySelectorAll('td[days][aria-label="' + dayNum + '"]');
						let clicked = false;

						for (const cell of cells) {{
							// Click on this day (prefer unfilled cells)
							if (!cell.classList.contains('{Selector.FILLED_DAY_CLASS}') && cell.onclick) {{
								cell.click();
								clickedDays.push(dayNum);
								clicked = true;
								break;
							}}
						}}

						// If not clicked yet, try any cell with this day number
						if (!clicked && cells.length > 0) {{
							for (const cell of cells) {{
								if (cell.onclick) {{
									cell.click();
									clickedDays.push(dayNum);
									clicked = true;
									break;
								}}
							}}
						}}

						if (!clicked) {{
							failedDays.push(dayNum);
						}}
					}}

					return {{ clickedDays, failedDays }};
				}}
			""",
				day_numbers,
			)

			if clicked.get('failedDays'):
				logger.warning('Could not click days: %s', clicked['failedDays'])

			if not clicked.get('clickedDays'):
				logger.error('Failed to select any days')
				return 0, len(records_to_fill)

			logger.debug('✓ Selected %d days', len(clicked['clickedDays']))
			self.page.wait_for_timeout(Timing.WAIT_AFTER_CLICK)

			# Step 3: Click "Selected Days" button to load all selected days into the table
			logger.debug('📋 Loading selected days into form...')
			btn = self.page.locator(f'input[value="{Buttons.SELECTED_DAYS}"]')
			if btn.count() > 0:
				btn.first.click()
				self.page.wait_for_timeout(Timing.WAIT_FOR_TABLE_LOAD)
				self.wait_for_load()
			else:
				logger.warning('Could not find "Selected Days" button')

			# Step 4: Fill all rows at once
			logger.debug('✍️  Filling all rows...')

			# Build mapping of day -> fill data
			fill_map = {}
			for record_date, entry_time, exit_time, work_type in records_to_fill:
				if not work_type.hilan_code:
					continue
				day_key = f'{record_date.day:02d}/{record_date.month:02d}'
				fill_map[day_key] = {
					'entry': entry_time.strftime('%H:%M'),
					'exit': exit_time.strftime('%H:%M'),
					'workCode': work_type.hilan_code,
				}

			result = self.page.evaluate(
				rf"""
				(fillMap) => {{
					const entryInputs = document.querySelectorAll('{Selector.ENTRY_INPUT}');
					const exitInputs = document.querySelectorAll('{Selector.EXIT_INPUT}');
					const symbolSelects = document.querySelectorAll('{Selector.WORK_TYPE_SELECT}');

					if (entryInputs.length === 0) {{
						return {{ success: false, error: 'No entry inputs found', filled: 0 }};
					}}

					let filled = 0;
					const errors = [];

					// First, gather all ReportDate cells from the main grid
					const allReportDateCells = document.querySelectorAll('[id*="ReportDate_row_"]');
					const dates = [];

					for (const cell of allReportDateCells) {{
						const text = cell.textContent?.trim();
						if (text && /^\d{{1,2}}\/\d{{1,2}}/.test(text)) {{
							const dateText = text.split(' ')[0]; // Get "19/12" part
							dates.push(dateText);
						}}
					}}

					// Now fill inputs by index - assume inputs are in same order as dates
					for (let i = 0; i < entryInputs.length; i++) {{
						try {{
							// Get the date for this row by index
							const dateText = dates[i];

							if (!dateText) {{
								errors.push('Row ' + i + ': No date found at this index (have ' + dates.length + ' dates total)');
								continue;
							}}

							// Check if we have fill data for this date
							const fillData = fillMap[dateText];
							if (!fillData) {{
								// This day wasn't in our fill list, skip it silently
								continue;
							}}

							// Fill entry time
							if (entryInputs[i]) {{
								entryInputs[i].value = fillData.entry;
								entryInputs[i].dispatchEvent(new Event('change', {{ bubbles: true }}));
								entryInputs[i].dispatchEvent(new Event('blur', {{ bubbles: true }}));
							}}

							// Fill exit time
							if (exitInputs[i]) {{
								exitInputs[i].value = fillData.exit;
								exitInputs[i].dispatchEvent(new Event('change', {{ bubbles: true }}));
								exitInputs[i].dispatchEvent(new Event('blur', {{ bubbles: true }}));
							}}

							// Set work type
							if (symbolSelects[i]) {{
								symbolSelects[i].value = fillData.workCode;
								symbolSelects[i].dispatchEvent(new Event('change', {{ bubbles: true }}));
							}}

							filled++;
						}} catch (err) {{
							errors.push('Row ' + i + ': ' + err.message);
						}}
					}}

					return {{
						success: filled > 0,
						filled: filled,
						totalRows: entryInputs.length,
						errors: errors
					}};
				}}
			""",
				fill_map,
			)

			if not result.get('success'):
				logger.error('Failed to fill any rows: %s', result.get('error', 'Unknown error'))
				return 0, len(records_to_fill)

			filled_count = result.get('filled', 0)
			total_rows = result.get('totalRows', 0)
			logger.debug('✓ Filled %d/%d rows', filled_count, total_rows)

			if result.get('errors') and len(result['errors']) > 0:
				logger.warning('%d warnings', len(result['errors']))

			self.page.wait_for_timeout(Timing.WAIT_AFTER_FILL)

			# Step 5: Click save button ONCE for all days
			logger.debug('💾 Saving all changes...')
			save_btn = self.page.locator(f'input[value="{Buttons.SAVE}"]')
			if save_btn.count() > 0 and save_btn.is_visible():
				save_btn.first.click()
				self.wait_for_load()
				self.page.wait_for_timeout(Timing.WAIT_AFTER_SAVE)
				logger.success('✓ Batch saved %d days successfully!', filled_count)

				failed_count = len(records_to_fill) - filled_count
				return filled_count, failed_count
			else:
				logger.warning('Could not find save button, trying alternative...')
				saved = self.page.evaluate(f"""
					() => {{
						const btn = document.querySelector('{Selector.SAVE_BUTTON}');
						if (btn) {{
							btn.click();
							return true;
						}}
						return false;
					}}
				""")

				if saved:
					self.wait_for_load()
					self.page.wait_for_timeout(Timing.WAIT_AFTER_SAVE)
					logger.success('✓ Batch saved %d days successfully!', filled_count)
					failed_count = len(records_to_fill) - filled_count
					return filled_count, failed_count
				else:
					logger.error('Could not trigger save')
					return 0, len(records_to_fill)

		except Exception as e:
			logger.error('Batch fill error: %s', e)
			return 0, len(records_to_fill)

	def _parse_calendar(self, year: int, month: int) -> list[AttendanceRecord]:
		"""Parse the Hilan calendar grid.

		Args:
			year: Year for date construction.
			month: Month for date construction.

		Returns:
			List of attendance records from the calendar view.
		"""
		records: list[AttendanceRecord] = []
		day_cells = self.page.locator('td[days]').all()

		for cell in day_cells:
			record = self._parse_day_cell(cell, year, month)
			if record:
				records.append(record)

		return records

	def _parse_day_cell(self, cell: Locator, year: int, month: int) -> Optional[AttendanceRecord]:
		"""Parse a single calendar day cell.

		Args:
			cell: Playwright locator for the day cell.
			year: Year for date construction.
			month: Month for date construction.

		Returns:
			AttendanceRecord or None if parsing failed.
		"""
		try:
			# Get day number
			day_num = None
			aria_label = cell.get_attribute('aria-label')
			if aria_label and aria_label.isdigit():
				day_num = int(aria_label)
			elif (dts := cell.locator('.dTS')).count() > 0 and (
				text := dts.first.inner_text().strip()
			).isdigit():
				day_num = int(text)

			if not day_num or day_num < 1 or day_num > 31:
				return None

			# Get time/status
			entry_time_value = None
			status_note = None

			title = cell.get_attribute('title')
			if title and not (entry_time_value := parse_time_string(title)):
				status_note = StatusNotes.detect_in(title)

			if (
				not entry_time_value
				and not status_note
				and (cdm := cell.locator('.cDM')).count() > 0
				and (text := cdm.first.inner_text().strip())
				and text != '\xa0'
				and not (entry_time_value := parse_time_string(text))
			):
				status_note = StatusNotes.detect_in(text)

			# Determine actual date (Hilan shows cross-month pay periods)
			cell_year, cell_month, cell_day = get_cell_date(
				day_num, month, year, self.config.pay_period_start_day
			)

			# Validate day exists in the determined month
			_, max_day = cal.monthrange(cell_year, cell_month)
			if cell_day > max_day:
				return None

			return AttendanceRecord(
				date=date(cell_year, cell_month, cell_day),
				entry_time=entry_time_value,
				exit_time=None,
				note=status_note,
			)

		except Exception as e:
			logger.debug('Failed to parse day cell: %s', e)
			return None
