-- ============================================================
-- F1 MCP App — Database Schema (OpenF1-native)
-- Telemetry, intervals, championship served live from OpenF1.
-- ============================================================

CREATE TABLE IF NOT EXISTS sessions (
    id                   SERIAL PRIMARY KEY,
    session_key          INTEGER UNIQUE NOT NULL,
    meeting_key          INTEGER,
    year                 INTEGER NOT NULL,
    location             VARCHAR(100) NOT NULL,
    country_name         VARCHAR(100),
    country_code         VARCHAR(10),
    circuit_short_name   VARCHAR(50),
    session_name         VARCHAR(50) NOT NULL,
    session_type         VARCHAR(20),
    date_start           TIMESTAMP,
    date_end             TIMESTAMP,
    gmt_offset           VARCHAR(10),
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS drivers (
    id             SERIAL PRIMARY KEY,
    session_id     INTEGER REFERENCES sessions(id),
    driver_number  INTEGER NOT NULL,
    name_acronym   VARCHAR(10),
    broadcast_name VARCHAR(100),
    full_name      VARCHAR(100),
    first_name     VARCHAR(50),
    last_name      VARCHAR(50),
    team_name      VARCHAR(100),
    team_colour    VARCHAR(20),
    headshot_url   TEXT,
    country_code   VARCHAR(10),
    -- From session_result / starting_grid
    position       INTEGER,
    grid_position  INTEGER,
    dnf            BOOLEAN,
    dns            BOOLEAN,
    dsq            BOOLEAN,
    status         VARCHAR(50),
    gap_to_leader  TEXT,
    number_of_laps INTEGER,
    race_duration  FLOAT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, driver_number)
);

CREATE TABLE IF NOT EXISTS laps (
    id                SERIAL PRIMARY KEY,
    session_id        INTEGER REFERENCES sessions(id),
    driver_number     INTEGER NOT NULL,
    name_acronym      VARCHAR(10),
    lap_number        INTEGER,
    lap_duration      FLOAT,
    date_start        TIMESTAMP,
    duration_sector_1 FLOAT,
    duration_sector_2 FLOAT,
    duration_sector_3 FLOAT,
    i1_speed          INTEGER,
    i2_speed          INTEGER,
    st_speed          INTEGER,
    is_pit_out_lap    BOOLEAN,
    -- From stints
    compound          VARCHAR(20),
    tyre_age_at_start INTEGER,
    stint_number      INTEGER,
    fresh_tyre        BOOLEAN,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pits (
    id            SERIAL PRIMARY KEY,
    session_id    INTEGER REFERENCES sessions(id),
    driver_number INTEGER NOT NULL,
    name_acronym  VARCHAR(10),
    lap_number    INTEGER,
    stop_duration FLOAT,
    lane_duration FLOAT,
    date          TIMESTAMP,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS overtakes (
    id                       SERIAL PRIMARY KEY,
    session_id               INTEGER REFERENCES sessions(id),
    overtaking_driver_number INTEGER,
    overtaken_driver_number  INTEGER,
    position                 INTEGER,
    date                     TIMESTAMP,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS weather (
    id                SERIAL PRIMARY KEY,
    session_id        INTEGER REFERENCES sessions(id),
    date              TIMESTAMP,
    air_temperature   FLOAT,
    humidity          FLOAT,
    pressure          FLOAT,
    rainfall          BOOLEAN,
    track_temperature FLOAT,
    wind_direction    INTEGER,
    wind_speed        FLOAT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS race_control (
    id               SERIAL PRIMARY KEY,
    session_id       INTEGER REFERENCES sessions(id),
    date             TIMESTAMP,
    category         VARCHAR(100),
    message          TEXT,
    flag             VARCHAR(20),
    scope            VARCHAR(50),
    sector           INTEGER,
    driver_number    INTEGER,
    lap_number       INTEGER,
    qualifying_phase INTEGER,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- User & conversation tables
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email      VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    plan       VARCHAR(20) DEFAULT 'free'
);

CREATE TABLE IF NOT EXISTS conversations (
    id         SERIAL PRIMARY KEY,
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    title      TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id              SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
    message         TEXT,
    role            VARCHAR(20),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tool_executions (
    id              SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    tool_name       VARCHAR(255) NOT NULL,
    tool_request    JSONB,
    tool_response   JSONB,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_sessions_year             ON sessions(year);
CREATE INDEX IF NOT EXISTS idx_laps_session_driver       ON laps(session_id, driver_number);
CREATE INDEX IF NOT EXISTS idx_drivers_session           ON drivers(session_id);
CREATE INDEX IF NOT EXISTS idx_weather_session           ON weather(session_id);
CREATE INDEX IF NOT EXISTS idx_race_control_session      ON race_control(session_id);
CREATE INDEX IF NOT EXISTS idx_pits_session              ON pits(session_id);
CREATE INDEX IF NOT EXISTS idx_overtakes_session         ON overtakes(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user        ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation     ON messages(conversation_id);
