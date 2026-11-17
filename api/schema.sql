-- Cinder City leaderboard. Run once in your MySQL database (phpMyAdmin: Import, or paste into the SQL tab).

CREATE TABLE IF NOT EXISTS cc_runs (
  id          CHAR(32)     NOT NULL PRIMARY KEY,          -- random ticket handed out when a game starts
  ip_hash     CHAR(64)     NOT NULL,
  chr         VARCHAR(16)  NOT NULL DEFAULT '',
  started_at  INT UNSIGNED NOT NULL,                      -- server clock, unix seconds
  last_at     INT UNSIGNED NOT NULL,                      -- server clock at the latest report
  levels_done TINYINT UNSIGNED NOT NULL DEFAULT 0,
  time_s      INT UNSIGNED NOT NULL DEFAULT 0,            -- play time reported so far
  kills       INT UNSIGNED NOT NULL DEFAULT 0,
  dist_m      INT UNSIGNED NOT NULL DEFAULT 0,
  flagged     TINYINT UNSIGNED NOT NULL DEFAULT 0,        -- 1 = a report broke a plausibility rule
  flag_note   VARCHAR(120) NOT NULL DEFAULT '',
  KEY ix_started (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cc_scores (
  id         INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  run_id     CHAR(32)     NOT NULL,
  name       VARCHAR(12)  NOT NULL,
  chr        VARCHAR(16)  NOT NULL DEFAULT '',
  finished   TINYINT UNSIGNED NOT NULL DEFAULT 0,         -- 1 = all five levels done
  time_s     INT UNSIGNED NOT NULL DEFAULT 0,
  kills      INT UNSIGNED NOT NULL DEFAULT 0,
  dist_m     INT UNSIGNED NOT NULL DEFAULT 0,
  hidden     TINYINT UNSIGNED NOT NULL DEFAULT 0,         -- 1 = not shown (flagged run, or hidden by the admin)
  note       VARCHAR(120) NOT NULL DEFAULT '',
  ip_hash    CHAR(64)     NOT NULL,
  created_at INT UNSIGNED NOT NULL,
  UNIQUE KEY ux_run (run_id),
  KEY ix_time (hidden, finished, time_s),
  KEY ix_kills (hidden, kills),
  KEY ix_dist (hidden, dist_m),
  KEY ix_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- internal visitor count: one row per address (keyed hash) and day; n = page loads that day.
-- The API also creates this table by itself the first time a visit is counted.
CREATE TABLE IF NOT EXISTS cc_visits (
  day     DATE         NOT NULL,
  ip_hash CHAR(64)     NOT NULL,
  n       INT UNSIGNED NOT NULL DEFAULT 1,
  PRIMARY KEY (day, ip_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- one row per request that is rate limited (ticket, score, admin login)
CREATE TABLE IF NOT EXISTS cc_hits (
  ip_hash CHAR(64)     NOT NULL,
  act     VARCHAR(8)   NOT NULL,
  t       INT UNSIGNED NOT NULL,
  KEY ix_hit (ip_hash, act, t),
  KEY ix_t (t)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
