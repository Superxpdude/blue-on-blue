import json
import logging
log = logging.getLogger("blueonblue")

__all__ = ["config"]

# Load the config file

def config_load_raw():
	try:
		with open("config/config.json", "r") as f:
			config = json.load(f)
	except:
		config = {} # If we can't load the config, create an empty dict
	return config

def config_init():
	"""Initializes the config with the default settings."""
	cfg = config_load_raw()
	cfg.setdefault("BOT",{})
	cfg["BOT"].setdefault("DESC", "Blue-on-Blue")
	cfg["BOT"].setdefault("CMD_PREFIXES", ["$$"])
	cfg["BOT"].setdefault("TOKEN")
	cfg["BOT"].setdefault("COGS", ["Users","ChatFilter","Fun","Missions","Pings","Punish","Verify"]) # Users needs to be loaded first
	
	cfg.setdefault("STEAM",{})
	cfg["STEAM"].setdefault("API_TOKEN")
	cfg["STEAM"].setdefault("GROUP")
	
	cfg.setdefault("SERVER",{})
	cfg["SERVER"].setdefault("ID",)
	cfg["SERVER"].setdefault("CHANNELS",{})
	cfg["SERVER"]["CHANNELS"].setdefault("MOD")
	cfg["SERVER"]["CHANNELS"].setdefault("CHECK_IN")
	cfg["SERVER"]["CHANNELS"].setdefault("ACTIVITY")
	cfg["SERVER"]["CHANNELS"].setdefault("BOT")
	cfg["SERVER"]["CHANNELS"].setdefault("MISSION_AUDIT")
	cfg["SERVER"].setdefault("ROLES",{})
	cfg["SERVER"]["ROLES"].setdefault("MEMBER")
	cfg["SERVER"]["ROLES"].setdefault("ADMIN")
	cfg["SERVER"]["ROLES"].setdefault("MODERATOR")
	cfg["SERVER"]["ROLES"].setdefault("MISSION_MAKERS")
	cfg["SERVER"]["ROLES"].setdefault("PUNISH")
	cfg["SERVER"]["ROLES"].setdefault("DEAD")
	
	cfg.setdefault("GITLAB",{})
	cfg["GITLAB"].setdefault("WEB_URL","https://gitlab.com")
	cfg["GITLAB"].setdefault("API_URL","https://gitlab.com/api/v4")
	cfg["GITLAB"].setdefault("API_TOKEN")
	cfg["GITLAB"].setdefault("PROJECTS",[])
	
	cfg.setdefault("GITHUB",{})
	cfg["GITHUB"].setdefault("WEB_URL","https://github.com")
	cfg["GITHUB"].setdefault("API_URL","https://api.github.com")
	cfg["GITHUB"].setdefault("API_USER")
	cfg["GITHUB"].setdefault("API_TOKEN")
	cfg["GITHUB"].setdefault("PROJECTS",[])
	
	cfg.setdefault("WEB",{})
	cfg["WEB"].setdefault("GITLAB-TOKEN","changeme")
	
	cfg.setdefault("MISSIONS",{})
	cfg["MISSIONS"].setdefault("SHEET",{})
	cfg["MISSIONS"]["SHEET"].setdefault("URL")
	cfg["MISSIONS"]["SHEET"].setdefault("WORKSHEET")
	cfg["MISSIONS"]["SHEET"].setdefault("API_TOKEN_FILE","config/google_api.json")
	cfg["MISSIONS"].setdefault("WIKI")

	# Write the config
	with open("config/config.json", "w") as f:
		json.dump(cfg, f, indent="\t")

config = config_load_raw()