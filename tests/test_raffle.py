import pytest
import cogs.raffle


@pytest.mark.parametrize(
	"input, expected",
	[
		pytest.param("Test", (("Test", 1),), id="single"),
		pytest.param("Test:2", (("Test", 2),), id="single_with_playercount"),
		pytest.param("Test,Test2,Test3,Test4", (("Test", 1), ("Test2", 1), ("Test3", 1), ("Test4", 1)), id="multiple"),
		pytest.param(
			"Test,Test2:4,Test3:3,Test4",
			(("Test", 1), ("Test2", 4), ("Test3", 3), ("Test4", 1)),
			id="multiple_with_playercount_1",
		),
		pytest.param(
			"Test:2,Test2:2,Test3:2,Test4:2",
			(("Test", 2), ("Test2", 2), ("Test3", 2), ("Test4", 2)),
			id="multiple_with_playercount_2",
		),
		pytest.param("Test,Test2:A,Test3,Test4", True, id="error_multiple"),
		pytest.param("Test:", True, id="error_single"),
	],
)
def test_parseRaffle(input: str, expected: tuple[tuple[str, int], ...] | bool):
	output = ()
	try:
		output = cogs.raffle.parseRaffleString(input)
	except cogs.raffle.RaffleParseError:
		# If we get an error, make sure we expected to get one
		assert isinstance(expected, bool)
		return

	# Make sure our output matches our expected output
	assert output == expected
