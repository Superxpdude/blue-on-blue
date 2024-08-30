# blueonblue Discord Bot
A discord bot written in Python for TMTM.

# Container Usage
The name of the container image is `ghcr.io/superxpdude/blueonblue`

Volume mount the data directory on the host to `/app/data` inside the container.

The data directory must contain a file named `google_api.json` which contains a Google API token for the mission schedule.

The bot will run as the root user in the container by default. Changing the user can be done via the `--user` flag on container creation.

## Backups
Backups can be performed using the following exec command.
```
podman exec *CONTAINERNAME* backup
```
The backup will perform a backup of the SQLite database, and place it within a datestamped zip file. Additionally, performing a backup automatically clears out any backups more than 14 days old.

For best results, run this command on a regular schedule using something like cron.

# Environment Variables
The following environment variables are used to configure the bot.

| Name | Required | Purpose |
|------|---------|---------|
| `COMMAND_PREFIX` | | Bot command prefix for text-based administration commands. |
| `DEBUG_LOGGING` | | Enables debug logging. |
| `DEBUG_SERVER` | | Debug server ID. Assigns bot commands to specific server instead of globally. |
| `DISCORD_TOKEN` | `True` | Discord bot token |
| `STEAM_TOKEN` | `True` | Steam API token |
| `TZ` | | Timezone to use. |
