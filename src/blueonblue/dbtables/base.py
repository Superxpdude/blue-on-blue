from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from ..db import DBConnection


class BaseTable:
	def __init__(self, db: "DBConnection"):
		self.db = db
