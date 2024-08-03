-- Revises: None
-- Creation Data: 2024-08-02
-- Reason: Initial database setup

CREATE TABLE arma_stats_missions (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	server_id INTEGER NOT NULL,
	api_id INTEGER NOT NULL,
	file_name TEXT NOT NULL,
	start_time TEXT NOT NULL,
	end_time TEXT NOT NULL,
	main_op INTEGER,
	UNIQUE(server_id,api_id)
);

CREATE TABLE arma_stats_players (
	mission_id INTEGER NOT NULL,
	steam_id INTEGER NOT NULL,
	duration REAL NOT NULL,
	UNIQUE(mission_id,steam_id),
	FOREIGN KEY (mission_id) REFERENCES arma_stats_missions (id) ON DELETE CASCADE
);

CREATE TABLE gold (
	server_id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	expiry_time INTEGER,
	UNIQUE(server_id,user_id)
);

CREATE TABLE pings (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	server_id INTEGER NOT NULL,
	ping_name TEXT NOT NULL,
	last_used_time INTEGER,
	alias_for INTEGER,
	UNIQUE(server_id,ping_name),
	FOREIGN KEY (alias_for) REFERENCES pings (id) ON DELETE CASCADE
);

CREATE TABLE ping_users (
	server_id INTEGER NOT NULL,
	ping_id INTEGER,
	user_id INTEGER NOT NULL,
	UNIQUE(server_id,ping_id,user_id),
	FOREIGN KEY (ping_id) REFERENCES pings (id) ON DELETE CASCADE
);

CREATE TABLE raffle_data (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	group_id INTEGER NOT NULL,
	title TEXT NOT NULL,
	winners INTEGER NOT NULL,
	FOREIGN KEY (group_id) REFERENCES raffle_groups (id) ON DELETE CASCADE
);

CREATE TABLE raffle_groups (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	server_id INTEGER NOT NULL,
	end_time TEXT NOT NULL,
	exclusive INTEGER NOT NULL,
	weighted INTEGER NOT NULL,
	message_id INT
);

CREATE TABLE raffle_users (
	raffle_id INTEGER NOT NULL,
	discord_id INTEGER NOT NULL,
	FOREIGN KEY (raffle_id) REFERENCES raffle_data (id) ON DELETE CASCADE
);

CREATE TABLE raffle_weights (
	server_id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	weight NUMERIC NOT NULL,
	UNIQUE(server_id, user_id)
);

CREATE TABLE serverconfig (
	server_id INTEGER,
	setting TEXT,
	value TEXT,
	UNIQUE(server_id, setting)
);

CREATE TABLE if NOT EXISTS verify (
	discord_id INTEGER PRIMARY KEY,
	steam64_id INTEGER UNIQUE
);

CREATE VIEW mission_attendance_view AS
	SELECT
		m.id,
		m.main_op,
		m.server_id,
		m.api_id,
		m.file_name,
		v.discord_id as discord_id,
		v.steam64_id,
		m.start_time,
		((julianday(m.end_time) - julianday(m.start_time)) * 1440)AS mission_duration,
		p.duration as player_session,
		(SELECT COUNT(*) FROM arma_stats_players pp WHERE pp.mission_id = m.id) as user_attendance
	FROM arma_stats_missions m
		INNER JOIN arma_stats_players p on p.mission_id = m.id
		INNER JOIN verify v on v.steam64_id = p.steam_id;

PRAGMA user_version = 1;
