import logging
import sys
from typing import Any

from rich.console import Console

__version__ = '1.0.0'
__all__ = ['__version__', 'logger', 'console', 'enable_debug_logging']


class CustomLogger(logging.Logger):
	"""Custom logger with success() method."""

	SUCCESS = 25  # Between INFO (20) and WARNING (30)

	class _ColoredFormatter(logging.Formatter):
		"""Custom formatter that adds colors based on log level."""

		# ANSI color codes
		COLORS = {
			logging.DEBUG: '\033[90m',  # Gray
			logging.INFO: '\033[0m',  # Default (no color)
			25: '\033[32m',  # Green (SUCCESS)
			logging.WARNING: '\033[33m',  # Yellow
			logging.ERROR: '\033[31m',  # Red
			logging.CRITICAL: '\033[1;31m',  # Bold Red
		}
		RESET = '\033[0m'

		def format(self, record: logging.LogRecord) -> str:
			message = super().format(record)
			# Use level-based colors
			color = self.COLORS.get(record.levelno, self.RESET)
			return f'{color}{message}{self.RESET}'

	def __init__(self, name: str, level: int = logging.NOTSET) -> None:
		super().__init__(name, level)
		# Register the custom level
		logging.addLevelName(self.SUCCESS, 'SUCCESS')

	def success(self, message: str, *args: Any, **kwargs: Any) -> None:
		"""Log a success message at SUCCESS level."""
		self.log(self.SUCCESS, message, *args, **kwargs)

	@classmethod
	def setup_logger(cls, name: str, level: int = logging.INFO) -> 'CustomLogger':
		"""Create and configure a logger with colored output."""
		logging.setLoggerClass(cls)
		logger = logging.getLogger(name)
		if not isinstance(logger, cls):
			raise TypeError(f'Expected {cls.__name__}, got {type(logger).__name__}')

		handler = logging.StreamHandler(sys.stderr)
		handler.setFormatter(cls._ColoredFormatter('%(message)s'))
		logger.addHandler(handler)
		logger.setLevel(level)

		return logger


# Set up module logger with colored output
logger = CustomLogger.setup_logger('hilan_attendance')

# Console for rich output (tables, panels)
console = Console()


def enable_debug_logging() -> None:
	"""Enable DEBUG level logging for verbose output."""
	logger.setLevel(logging.DEBUG)
