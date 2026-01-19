"""Base page class with common utilities (internal module)."""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, ClassVar

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from ... import logger

if TYPE_CHECKING:
	from ...models import Config
	from ..session import BrowserSession


class BasePage(ABC):
	"""Abstract base class for page objects. Cannot be instantiated directly.

	Subclasses must define the PATH class variable.
	"""

	PATH: ClassVar[str]  # Subclasses must define this

	@classmethod
	def __init_subclass__(cls, **kwargs: object) -> None:
		"""Validate that subclasses define PATH."""
		super().__init_subclass__(**kwargs)
		if not hasattr(cls, 'PATH') or cls.PATH == '':
			raise TypeError(f'{cls.__name__} must define a non-empty PATH class variable')

	def __init__(self, session: BrowserSession) -> None:
		if type(self) is BasePage:
			raise TypeError('_BasePage cannot be instantiated directly; use a subclass')
		self._session = session

	@property
	def session(self) -> BrowserSession:
		"""Get the browser session."""
		return self._session

	@property
	def page(self) -> Page:
		"""Get the Playwright page."""
		return self._session.page

	@property
	def config(self) -> Config:
		"""Get the configuration."""
		return self._session.config

	@property
	def url(self) -> str:
		"""Get the full URL for this page."""
		base = str(self.config.url).rstrip('/')
		return base + self.PATH

	def is_current(self) -> bool:
		"""Check if the browser is currently on this page.

		Uses startswith to allow for query parameters and fragments.
		"""
		return self.page.url.lower().startswith(self.url.lower())

	def navigate_to(self) -> None:
		"""Navigate to this page."""
		self.page.goto(self.url)
		self.wait_for_load()

	def wait_for_load(self) -> None:
		"""Wait for the page to fully load.

		Waits for multiple load states to ensure page is completely ready:
		- domcontentloaded: DOM is fully parsed
		- load: All resources (images, scripts, etc.) are loaded
		- networkidle: No network requests for at least 500ms
		"""
		self.page.wait_for_load_state('domcontentloaded')
		self.page.wait_for_load_state('load')
		self.page.wait_for_load_state('networkidle')

	def try_fill(self, selector: str, value: str, silent: bool = False) -> bool:
		"""Try to fill a field using a selector string.

		Args:
			selector: CSS selector to try.
			value: Value to fill.
			silent: If True, don't print failure messages.

		Returns:
			True if field was filled successfully.
		"""
		if self.page.locator(selector).count() <= 0:
			return False
		try:
			self.page.fill(selector, value)
			return True
		except PlaywrightError as e:
			if not silent:
				logger.debug('Failed to fill field with selector %s: %s', selector, e)
			return False

	def try_click(self, selector: str, silent: bool = False) -> bool:
		"""Try to click an element using a selector string.

		Args:
			selector: CSS selector to try.
			silent: If True, don't print failure messages.

		Returns:
			True if element was clicked successfully.
		"""
		if self.page.locator(selector).count() <= 0:
			return False
		try:
			self.page.click(selector)
			return True
		except PlaywrightError as e:
			if not silent:
				logger.debug('Failed to click selector %s: %s', selector, e)
			return False
