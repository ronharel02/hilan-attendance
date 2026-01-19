"""Login page automation for Hilan."""

from enum import StrEnum

from ... import logger
from .base import BasePage

# Timing constant (milliseconds)
WAIT_AFTER_LOGIN_MS = 1000


class Selector(StrEnum):
	"""CSS selectors for login form elements."""

	USERNAME = 'input[type="text"]'
	PASSWORD = 'input[type="password"]'
	SUBMIT = 'button[type="submit"]'


class LoginPage(BasePage):
	"""Handles Hilan login page interactions."""

	PATH = '/login'

	def login(self) -> bool:
		"""Perform login action using credentials from config.

		Note: This only performs the login action. The caller (HilanBrowser)
		is responsible for validating that we landed on the expected page.

		Returns:
			True if login form was submitted successfully.
		"""
		logger.info('🔐 Logging in to Hilan...')

		self.navigate_to()

		# Fill username
		if not self.try_fill(Selector.USERNAME, self.config.username):
			logger.error('Could not find username field')
			return False

		# Fill password
		if not self.try_fill(Selector.PASSWORD, self.config.password.get_secret_value()):
			logger.error('Could not find password field')
			return False

		# Submit the form
		if not self.try_click(Selector.SUBMIT):
			logger.error('Could not find submit button')
			return False

		self.wait_for_load()
		self.page.wait_for_timeout(WAIT_AFTER_LOGIN_MS)

		return True
