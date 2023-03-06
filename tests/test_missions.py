import cogs.missions


def test_decode_Success():
	result = cogs.missions._decode_file_name("coop_53_daybreak_v1_3.Altis.pbo")
	assert result is not None
	assert result["gameType"] == "coop"
	assert result["map"] == "altis"
	assert result["playerCount"] == 53


def test_decode_errorNotPBO():
	try:
		cogs.missions._decode_file_name("coop_53_daybreak_v1_3.Altis")
	except Exception as e:
		assert isinstance(e,Exception)


def test_decode_errorPeriod():
	try:
		cogs.missions._decode_file_name("coop_53_daybreak_v1.3.Altis.pbo")
	except Exception as e:
		assert isinstance(e,Exception)


def test_decode_errorNoGameType():
	try:
		cogs.missions._decode_file_name("53_daybreak_v1_3.Altis.pbo")
	except Exception as e:
		assert isinstance(e,Exception)


def test_decode_errorNoPlayerCount():
	try:
		cogs.missions._decode_file_name("coop_daybreak_v1_3.Altis.pbo")
	except Exception as e:
		assert isinstance(e,Exception)


def test_decode_errorBadGameType():
	try:
		cogs.missions._decode_file_name("oop_53_daybreak_v1_3.Altis.pbo")
	except Exception as e:
		assert isinstance(e,Exception)
