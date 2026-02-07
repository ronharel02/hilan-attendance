"""High-level browser automation for Hilan attendance system."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .. import logger
from .pages import CalendarPage, HomePage, LoginPage
from .session import BrowserSession

if TYPE_CHECKING:
	from ..models import Config, FillInstruction, MonthAttendance


class HilanBrowser:
	"""High-level browser automation for Hilan attendance system.

	This class orchestrates navigation between pages and validates
	that transitions land on the expected pages.

	Example:
		with HilanBrowser(config) as browser:
			if browser.login():
				browser.navigate_to_attendance()
				attendance = browser.get_attendance(2025, 1)
				browser.fill_batch_attendance(records)
	"""

	def __init__(self, config: Config) -> None:
		"""Initialize the browser with configuration.

		Args:
			config: Application configuration including credentials and URLs.
		"""
		self._session = BrowserSession(config)
		self._login_page: Optional[LoginPage] = None
		self._home_page: Optional[HomePage] = None
		self._calendar_page: Optional[CalendarPage] = None

	def __enter__(self) -> HilanBrowser:
		"""Start the browser session."""
		self._session.start()
		return self

	def __exit__(self, *exc) -> None:
		"""Stop the browser session."""
		self._session.stop()

	@property
	def login_page(self) -> LoginPage:
		"""Get the login page object (lazy initialization)."""
		if self._login_page is None:
			self._login_page = LoginPage(self._session)
		return self._login_page

	@property
	def home_page(self) -> HomePage:
		"""Get the home page object (lazy initialization)."""
		if self._home_page is None:
			self._home_page = HomePage(self._session)
		return self._home_page

	@property
	def calendar_page(self) -> CalendarPage:
		"""Get the calendar page object (lazy initialization)."""
		if self._calendar_page is None:
			self._calendar_page = CalendarPage(self._session)
		return self._calendar_page

	# =========================================================================
	# High-level methods (orchestrate page objects and validate transitions)
	# =========================================================================

	def login(self) -> bool:
		"""Log in to Hilan and validate landing on home page.

		Returns:
			True if login was successful and we landed on the home page.
		"""
		if not self.login_page.login():
			return False

		# Validate we landed on home page
		if not self.home_page.is_current():
			logger.error('Login failed - unexpected redirect to: %s', self._session.page.url)
			return False

		logger.success('✓ Login successful!')
		self._session.is_logged_in = True
		return True

	def navigate_to_attendance(self) -> None:
		"""Navigate to the attendance page and validate."""
		logger.info('📋 Navigating to attendance page...')
		self.calendar_page.navigate_to()

		if not self.calendar_page.is_current():
			logger.warning('May not be on calendar page. Current URL: %s', self._session.page.url)
		else:
			logger.success('✓ Navigated to attendance page')

	def get_attendance(self, year: int, month: int) -> Optional[MonthAttendance]:
		"""Get attendance data for a specific month.

		Args:
			year: Year to fetch.
			month: Month to fetch (1-12).

		Returns:
			MonthAttendance with all records, or None if navigation failed.
		"""
		return self.calendar_page.get_attendance(year, month)

	def fill_batch_attendance(
		self,
		records_to_fill: list[FillInstruction],
		dry_run: bool = False,
	) -> tuple[int, int]:
		"""Fill attendance for multiple days in one batch.

		Args:
			records_to_fill: List of fill instructions.
			dry_run: If True, show what would be done without actually doing it.

		Returns:
			Tuple of (successful_count, failed_count).
		"""
		return self.calendar_page.fill_batch(records_to_fill, dry_run=dry_run)
