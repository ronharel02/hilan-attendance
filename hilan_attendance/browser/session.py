"""Browser session management for Hilan automation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from playwright.sync_api import (
	Browser,
	BrowserContext,
	Page,
	Playwright,
	sync_playwright,
)

if TYPE_CHECKING:
	from ..models import Config


class BrowserSession:
	"""Manages browser lifecycle and shared state.

	This class handles the Playwright browser instance and provides
	a shared Page object for all page classes to use.
	"""

	def __init__(self, config: Config) -> None:
		self.config = config
		self._playwright: Optional[Playwright] = None
		self._browser: Optional[Browser] = None
		self._context: Optional[BrowserContext] = None
		self._page: Optional[Page] = None
		self._is_logged_in = False

	def start(self) -> None:
		"""Start the browser session."""
		self._playwright = sync_playwright().start()
		self._browser = self._playwright.chromium.launch(
			headless=self.config.headless,
			slow_mo=self.config.slow_mo,
		)
		self._context = self._browser.new_context(
			viewport={'width': 1280, 'height': 800},
			locale='he-IL',
		)
		self._page = self._context.new_page()

	def stop(self) -> None:
		"""Stop the browser session and clean up resources."""
		if self._page:
			self._page.close()
			self._page = None
		if self._context:
			self._context.close()
			self._context = None
		if self._browser:
			self._browser.close()
			self._browser = None
		if self._playwright:
			self._playwright.stop()
			self._playwright = None
		self._is_logged_in = False

	@property
	def page(self) -> Page:
		"""Get the current page.

		Raises:
			RuntimeError: If session hasn't been started.
		"""
		if self._page is None:
			raise RuntimeError('Browser session not started. Call start() first.')
		return self._page

	@property
	def is_logged_in(self) -> bool:
		"""Check if user is logged in."""
		return self._is_logged_in

	@is_logged_in.setter
	def is_logged_in(self, value: bool) -> None:
		"""Set login state."""
		self._is_logged_in = value

	def __enter__(self) -> BrowserSession:
		"""Context manager entry - starts the session."""
		self.start()
		return self

	def __exit__(self, *exc) -> None:
		"""Context manager exit - stops the session."""
		self.stop()
