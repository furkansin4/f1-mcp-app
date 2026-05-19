-- ============================================================
-- F1 MCP App — Database Schema
-- Telemetry is served live from OpenF1 API; not stored here.
-- ============================================================

CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    season INTEGER NOT NULL,
    event_name VARCHAR(100) NOT NULL,
    session_name VARCHAR(50) NOT NULL,
    date TIMESTAMP,
    api_path VARCHAR(200),
    session_info JSONB,
    f1_api_support BOOLEAN,
    total_laps INTEGER,
    session_start_time INTERVAL,
    t0_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(season, event_name, session_name)
);

CREATE TABLE IF NOT EXISTS drivers (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions(id),
    driver_number VARCHAR(10) NOT NULL,
    broadcast_name VARCHAR(100),
    full_name VARCHAR(100),
    driver_id VARCHAR(10),
    driver_name VARCHAR(50),
    team_name VARCHAR(100),
    team_color VARCHAR(20),
    team_id VARCHAR(50),
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    headshot_url TEXT,
    country_code VARCHAR(10),
    position FLOAT,
    classified_position VARCHAR(10),
    grid_position FLOAT,
    q1_time INTERVAL,
    q2_time INTERVAL,
    q3_time INTERVAL,
    race_time INTERVAL,
    status VARCHAR(100),
    points FLOAT,
    dnf BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, driver_number)
);

CREATE TABLE IF NOT EXISTS laps (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions(id),
    driver_id VARCHAR(10) NOT NULL,
    lap_number FLOAT,
    lap_time INTERVAL,
    lap_start_time INTERVAL,
    lap_start_date TIMESTAMP,
    stint FLOAT,
    pit_out_time INTERVAL,
    pit_in_time INTERVAL,
    sector1_time INTERVAL,
    sector2_time INTERVAL,
    sector3_time INTERVAL,
    sector1_session_time INTERVAL,
    sector2_session_time INTERVAL,
    sector3_session_time INTERVAL,
    speed_i1 FLOAT,
    speed_i2 FLOAT,
    speed_fl FLOAT,
    speed_st FLOAT,
    is_personal_best BOOLEAN,
    compound VARCHAR(50),
    tyre_life FLOAT,
    fresh_tyre BOOLEAN,
    team VARCHAR(100),
    track_status VARCHAR(50),
    position FLOAT,
    deleted BOOLEAN,
    deleted_reason TEXT,
    fastf1_generated BOOLEAN,
    is_accurate BOOLEAN,
    session_time INTERVAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS weather (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions(id),
    session_time INTERVAL,
    air_temp FLOAT,
    humidity FLOAT,
    pressure FLOAT,
    rainfall BOOLEAN,
    track_temp FLOAT,
    wind_direction INTEGER,
    wind_speed FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS session_status (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions(id),
    session_time INTERVAL,
    status VARCHAR(50),
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS track_status (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions(id),
    session_time INTERVAL,
    status VARCHAR(10),
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS race_control (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions(id),
    utc TIMESTAMP,
    category VARCHAR(100),
    message TEXT,
    status VARCHAR(50),
    flag VARCHAR(20),
    scope VARCHAR(50),
    sector VARCHAR(10),
    racing_number VARCHAR(20),
    lap INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS circuit_info (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions(id),
    info_type VARCHAR(50),
    x_position FLOAT,
    y_position FLOAT,
    number INTEGER,
    letter VARCHAR(10),
    angle FLOAT,
    distance FLOAT,
    rotation FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- User & conversation tables
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    plan VARCHAR(20) DEFAULT 'free'
);

CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
    message TEXT,
    role VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tool_executions (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    tool_name VARCHAR(255) NOT NULL,
    tool_request JSONB,
    tool_response JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_laps_session_driver    ON laps(session_id, driver_id);
CREATE INDEX IF NOT EXISTS idx_drivers_session        ON drivers(session_id);
CREATE INDEX IF NOT EXISTS idx_weather_session        ON weather(session_id);
CREATE INDEX IF NOT EXISTS idx_race_control_session   ON race_control(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user     ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation  ON messages(conversation_id);
