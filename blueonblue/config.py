import json

__all__ = ["config"]

# Load the config file
try:
	with open("config/config.json", "r") as f:
		config = json.load(f)
except:
	config = {} # If we can't load the config, create an empty dict

def init_config():
	# Set default values
	config.setdefault("BOT",{})
	config["BOT"].setdefault("DESC", "Blue-on-Blue")
	config["BOT"].setdefault("CMD_PREFIXES", ["$$"])
	config["BOT"].setdefault("TOKEN")
	config["BOT"].setdefault("COGS", ["BotControl","ChatFilter","Missions","Pings","Punish","Verify"])

	config.setdefault("STEAM",{})
	config["STEAM"].setdefault("API_TOKEN")
	config["STEAM"].setdefault("GROUP")

	config.setdefault("SERVER",{})
	config["SERVER"].setdefault("ID")
	config["SERVER"].setdefault("CHANNELS",{})
	config["SERVER"]["CHANNELS"].setdefault("MOD")
	config["SERVER"]["CHANNELS"].setdefault("CHECK_IN")
	config["SERVER"]["CHANNELS"].setdefault("ACTIVITY")
	config["SERVER"]["CHANNELS"].setdefault("BOT")
	config["SERVER"]["CHANNELS"].setdefault("MISSION_AUDIT")
	config["SERVER"].setdefault("ROLES",{})
	config["SERVER"]["ROLES"].setdefault("MEMBER")
	config["SERVER"]["ROLES"].setdefault("ADMIN")
	config["SERVER"]["ROLES"].setdefault("MODERATOR")
	config["SERVER"]["ROLES"].setdefault("MISSION_MAKERS")
	config["SERVER"]["ROLES"].setdefault("PUNISH")
	config["SERVER"]["ROLES"].setdefault("DEAD")

	config.setdefault("GITLAB",{})
	config["GITLAB"].setdefault("WEB_URL","https://gitlab.com")
	config["GITLAB"].setdefault("API_URL","https://gitlab.com/api/v4")
	config["GITLAB"].setdefault("API_TOKEN")
	config["GITLAB"].setdefault("PROJECTS",[])

	config.setdefault("GITHUB",{})
	config["GITHUB"].setdefault("WEB_URL","https://github.com")
	config["GITHUB"].setdefault("API_URL","https://api.github.com")
	config["GITHUB"].setdefault("API_USER")
	config["GITHUB"].setdefault("API_TOKEN")
	config["GITHUB"].setdefault("PROJECTS",[])

	config.setdefault("MISSIONS",{})
	config["MISSIONS"].setdefault("SHEET",{})
	config["MISSIONS"]["SHEET"].setdefault("URL")
	config["MISSIONS"]["SHEET"].setdefault("WORKSHEET")
	config["MISSIONS"]["SHEET"].setdefault("API_TOKEN_FILE")
	config["MISSIONS"].setdefault("WIKI")

	# Write the config
	with open("config/config.json", "w") as f:
		json.dump(config, f, indent="\t")