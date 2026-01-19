"""Home page - post-login landing page."""

from .base import BasePage


class HomePage(BasePage):
	"""Post-login landing page.

	After successful login, Hilan redirects to this personal file home page.
	This class serves as validation that login succeeded.
	"""

	PATH = '/Hilannetv2/ng/personal-file/home'
