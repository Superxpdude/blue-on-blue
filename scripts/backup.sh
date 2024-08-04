#!/bin/bash
# Container backup script
# Automatically backs up the SQLite database to an archive
# Ensure that the backups directory exists
mkdir -p /app/data/backups

# Create the SQLite backup
echo "Starting backup"
sqlite3 /app/data/blueonblue.sqlite3 ".backup /tmp/blueonblue.sqlite3"

# Create the zip file
echo "Creating zip file"
zip -j -r "/app/data/backups/blueonblue-$(date +"%Y-%m-%d-%H-%M").zip" /tmp/blueonblue.sqlite3

# Remove the temporary file
echo "Cleaning temporary files"
rm /tmp/blueonblue.sqlite3

# Clear all backups older than 14 days
echo "Cleaning old backups"
find /app/data/backups -type f -mtime +14 -name "*.zip" -maxdepth 1 -delete
echo "Backup complete"
