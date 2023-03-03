import cogs.missions

def test_parseSuccess():
	result = cogs.missions._decode_file_name("coop_53_daybreak_v1_3.Altis.pbo")
	assert result is not None

def test_parseError():
	try:
		cogs.missions._decode_file_name("coop_53_daybreak_v1.3.Altis.pbo")
	except Exception as e:
		assert isinstance(e,Exception)
