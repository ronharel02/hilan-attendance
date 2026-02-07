"""Pydantic models for configuration and attendance data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from enum import Enum
from typing import Optional

from pydantic import (
	BaseModel,
	Field,
	HttpUrl,
	SecretStr,
	field_serializer,
	model_validator,
)

from .vocabulary import Weekdays


class WorkType(str, Enum):
	"""Type of work location."""

	OFFICE = 'office'
	HOME = 'home'
	ABROAD = 'abroad'
	SKIP = 'skip'  # Non-work day

	@property
	def label(self) -> str:
		"""Human-readable label (e.g., 'Office', 'Home')."""
		return self.value.title()

	@property
	def hilan_code(self) -> Optional[str]:
		"""Hilan work type code (used when filling)."""
		return {
			WorkType.OFFICE: '103',
			WorkType.HOME: '101',
			WorkType.ABROAD: '104',
		}.get(self)

	@classmethod
	def from_hilan_code(cls: type[WorkType], code: str) -> Optional[WorkType]:
		"""Convert Hilan's work type code into a WorkType."""
		return {
			'103': cls.OFFICE,
			'101': cls.HOME,
			'104': cls.ABROAD,
		}.get(code)


@dataclass(frozen=True, slots=True)
class FillInstruction:
	"""Internal instruction for filling a specific attendance day."""

	type: WorkType
	date: date
	entry_time: Optional[time]
	exit_time: Optional[time]


class AttendancePattern(BaseModel):
	"""Default attendance pattern with per-day work types."""

	entry_time: time = Field(default=time(9, 0))
	exit_time: time = Field(default=time(18, 0))
	days: dict[Weekdays, WorkType] = Field(
		default_factory=lambda: {
			Weekdays.SUNDAY: WorkType.OFFICE,
			Weekdays.MONDAY: WorkType.OFFICE,
			Weekdays.TUESDAY: WorkType.OFFICE,
			Weekdays.WEDNESDAY: WorkType.OFFICE,
			Weekdays.THURSDAY: WorkType.OFFICE,
		}
	)

	@model_validator(mode='after')
	def validate_times(self) -> AttendancePattern:
		"""Ensure exit_time is after entry_time."""
		if self.exit_time <= self.entry_time:
			raise ValueError('exit_time must be after entry_time')
		return self

	@property
	def work_days(self) -> frozenset[int]:
		"""Get work day numbers as a set for fast membership checks."""
		return frozenset(
			day.number for day, work_type in self.days.items() if work_type != WorkType.SKIP
		)

	def get_work_type(self, weekday: int) -> Optional[WorkType]:
		"""Get work type for a weekday number."""
		day = Weekdays.from_number(weekday)
		if day and day in self.days and (wt := self.days[day]) != WorkType.SKIP:
			return wt
		return None


def get_pay_period(for_date: date, start_day: int) -> tuple[int, int]:
	"""Calculate which pay period a date belongs to.

	Args:
		for_date: The date to check.
		start_day: Day of month when pay period starts (e.g., 20 for 20th-19th periods).

	Returns:
		Tuple of (year, month) representing the pay period.
		If for_date.day >= start_day, we're in next month's pay period.
		E.g., on Dec 21 with start_day=20, returns (next_year, 1) for January's pay period.
	"""
	if for_date.day >= start_day:
		# We're in next month's pay period
		if for_date.month == 12:
			return for_date.year + 1, 1
		return for_date.year, for_date.month + 1
	return for_date.year, for_date.month


class Config(BaseModel):
	"""Main configuration."""

	username: str
	password: SecretStr
	url: HttpUrl
	pattern: AttendancePattern = Field(default_factory=AttendancePattern)
	headless: bool = True
	slow_mo: int = Field(default=500, ge=0)
	pay_period_start_day: int = Field(default=20, ge=1, le=28)

	@field_serializer('password', when_used='json')
	def serialize_password(self, password: SecretStr) -> str:
		"""Serialize SecretStr to plain string for JSON output."""
		return password.get_secret_value()

	@property
	def pay_period(self) -> tuple[int, int]:
		"""Get the current pay period's (year, month) based on today's date."""
		return get_pay_period(date.today(), self.pay_period_start_day)


class AttendanceRecord(BaseModel):
	"""A single attendance record."""

	date: date
	entry_time: Optional[time] = None
	exit_time: Optional[time] = None
	work_type: Optional[WorkType] = None
	note: Optional[str] = None

	@property
	def has_existing_entry(self) -> bool:
		"""Whether an entry time was recorded."""
		return self.entry_time is not None

	@property
	def has_existing_exit(self) -> bool:
		"""Whether an exit time was recorded."""
		return self.exit_time is not None

	@property
	def is_empty(self) -> bool:
		"""Whether no times are recorded."""
		return not self.has_existing_entry and not self.has_existing_exit

	@property
	def is_complete(self) -> bool:
		"""Whether both entry and exit times are recorded."""
		return self.has_existing_entry and self.has_existing_exit

	@property
	def needs_filling(self) -> bool:
		"""Whether this record needs to be filled."""
		return not self.is_complete and not self.note


class MonthAttendance(BaseModel):
	"""Attendance data for a month."""

	year: int
	month: int
	records: list[AttendanceRecord] = Field(default_factory=list)
