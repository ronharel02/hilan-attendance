"""Vocabulary for Hilan UI - Hebrew and English strings.

Named in spirit after Eliezer Ben-Yehuda, the father of modern Hebrew.
Centralizes all UI strings, labels, and translations used in the application.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Optional


class Buttons(StrEnum):
	"""Hebrew UI button labels."""

	CLEAR = 'ניקוי'
	SELECTED_DAYS = 'ימים נבחרים'
	SAVE = 'שמירה'


class StatusNotes(StrEnum):
	"""Hebrew status notes shown in calendar cells."""

	SICK = 'מחלה'
	VACATION = 'חופשה'
	VACATION_ALT = 'חופש'  # Alternative spelling
	HOLIDAY = 'חג'

	@classmethod
	def _members(cls) -> list[StatusNotes]:
		"""Get all members as a list."""
		return list(cls.__members__.values())

	@property
	def canonical(self) -> StatusNotes:
		"""Get the canonical form (maps _ALT variants to their base)."""
		if self.name.endswith('_ALT'):
			base_name = self.name[:-4]  # Remove '_ALT'
			return StatusNotes[base_name]
		return self

	@classmethod
	def detect_in(cls, text: str) -> Optional[StatusNotes]:
		"""Detect any status note in the given text.

		Returns the canonical form (e.g., VACATION_ALT returns VACATION).
		"""
		for note in cls._members():
			if note.value in text:
				return note.canonical
		return None


class AriaLabels(StrEnum):
	"""Hebrew aria-label patterns for form inputs."""

	ENTRY = 'כניסה'  # "Entry"
	EXIT = 'יציאה'  # "Exit"
	REPORT_TYPE = 'סוג דיווח'  # "Report type"


class Months(StrEnum):
	"""Month names in Hebrew and English."""

	JANUARY = 'ינואר'
	FEBRUARY = 'פברואר'
	MARCH = 'מרץ'
	APRIL = 'אפריל'
	MAY = 'מאי'
	JUNE = 'יוני'
	JULY = 'יולי'
	AUGUST = 'אוגוסט'
	SEPTEMBER = 'ספטמבר'
	OCTOBER = 'אוקטובר'
	NOVEMBER = 'נובמבר'
	DECEMBER = 'דצמבר'

	@property
	def english(self) -> str:
		"""Get the English month name (lowercase)."""
		return self.name.lower()

	@classmethod
	def _members(cls) -> list[Months]:
		"""Get all members as a list (workaround for ty type checker)."""
		return list(cls.__members__.values())

	@classmethod
	def from_number(cls, month: int) -> Optional[Months]:
		"""Get month from number (1-12)."""
		members = cls._members()
		if 1 <= month <= len(members):
			return members[month - 1]
		return None

	@classmethod
	def to_number(cls, name: str) -> Optional[int]:
		"""Get month number from Hebrew month name."""
		for i, m in enumerate(cls._members(), start=1):
			if m.value == name:
				return i
		return None

	@classmethod
	def from_english(cls, name: str) -> Optional[Months]:
		"""Get month from English name (case-insensitive, prefix match)."""
		name_lower = name.lower()
		matches = [m for m in cls._members() if m.english.startswith(name_lower)]
		return matches[0] if len(matches) == 1 else None

	@classmethod
	def all_hebrew(cls) -> list[str]:
		"""Get all Hebrew month names."""
		return [m.value for m in cls._members()]

	@classmethod
	def all_english(cls) -> list[str]:
		"""Get all English month names (lowercase)."""
		return [m.english for m in cls._members()]


class Weekdays(StrEnum):
	"""Weekday names (matching Python's datetime.weekday() where Monday=0)."""

	MONDAY = 'monday'
	TUESDAY = 'tuesday'
	WEDNESDAY = 'wednesday'
	THURSDAY = 'thursday'
	FRIDAY = 'friday'
	SATURDAY = 'saturday'
	SUNDAY = 'sunday'

	@classmethod
	def _members(cls) -> list[Weekdays]:
		"""Get all members as a list (workaround for ty type checker)."""
		return list(cls.__members__.values())

	@property
	def short(self) -> str:
		"""Get 3-letter abbreviation (Mon, Tue, etc.)."""
		return self.value[:3].title()

	@property
	def number(self) -> int:
		"""Get Python weekday number (Monday=0, Sunday=6)."""
		return self._members().index(self)

	@classmethod
	def from_number(cls, num: int) -> Optional[Weekdays]:
		"""Get weekday from Python weekday number (Monday=0, Sunday=6)."""
		members = cls._members()
		if 0 <= num < len(members):
			return members[num]
		return None

	@classmethod
	def from_name(cls, name: str) -> Optional[Weekdays]:
		"""Get weekday from name (case-insensitive)."""
		name_lower = name.lower()
		for day in cls._members():
			if day.value == name_lower:
				return day
		return None

	@classmethod
	def all_names(cls) -> list[str]:
		"""Get all weekday names (lowercase)."""
		return [d.value for d in cls._members()]

	@classmethod
	def all_short(cls) -> list[str]:
		"""Get all 3-letter abbreviations (Mon, Tue, etc.)."""
		return [d.short for d in cls._members()]


class DayTypes(StrEnum):
	"""Hebrew day type labels (for special days like sick, vacation, etc.)."""

	SICK = 'מחלה'
	VACATION = 'חופשה'
	HALF_VACATION = 'חצי חופשה'
	HOLIDAY = 'חג'
	RESERVE = 'מילואים'
	TRAINING = 'השתלמות'
	BEREAVEMENT = 'אבל'

	@classmethod
	def _members(cls) -> list[DayTypes]:
		"""Get all members as a list (workaround for ty type checker)."""
		return list(cls.__members__.values())

	@property
	def english(self) -> str:
		"""Get the English translation."""
		match self:
			case DayTypes.SICK:
				return 'Sick'
			case DayTypes.VACATION:
				return 'Vacation'
			case DayTypes.HALF_VACATION:
				return 'Half Vacation'
			case DayTypes.HOLIDAY:
				return 'Holiday'
			case DayTypes.RESERVE:
				return 'Reserve'
			case DayTypes.TRAINING:
				return 'Training'
			case DayTypes.BEREAVEMENT:
				return 'Bereavement'
			case _:
				return self.value  # Fallback to Hebrew value

	@classmethod
	def to_english(cls, hebrew: str) -> str:
		"""Translate a Hebrew day type to English. Returns original if not found."""
		for day_type in cls._members():
			if day_type.value == hebrew:
				return day_type.english
		return hebrew
