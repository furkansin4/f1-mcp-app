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
    driver_id VARCHAR(10), -- abbrevation
    driver_name VARCHAR(50), -- driver_id
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
    driver_id VARCHAR(10) NOT NULL, -- driver_number
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

CREATE TABLE IF NOT EXISTS telemetry (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions(id),
    driver_id VARCHAR(10) NOT NULL, -- driver_number
    driver_number VARCHAR(10) NOT NULL,
    lap_number FLOAT,
    session_time INTERVAL,
    date_time TIMESTAMP,
    time_elapsed INTERVAL,
    speed FLOAT,
    rpm FLOAT,
    n_gear INTEGER,
    throttle FLOAT,
    brake BOOLEAN,
    drs INTEGER,
    x_position FLOAT,
    y_position FLOAT,
    z_position FLOAT,
    status VARCHAR(20),
    source VARCHAR(20),
    distance FLOAT,
    relative_distance FLOAT,
    driver_ahead VARCHAR(10),
    distance_to_driver_ahead FLOAT,
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
    info_type VARCHAR(50), -- 'corners', 'marshal_lights', 'marshal_sectors'
    x_position FLOAT,
    y_position FLOAT,
    number INTEGER,
    letter VARCHAR(10),
    angle FLOAT,
    distance FLOAT,
    rotation FLOAT, -- Only for circuit rotation info
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
	title TEXT,
	created_at TIMESTAMP
);


CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
	conversation_id INTEGER REFERENCES conversations(id),
	message TEXT,
	role VARCHAR(20),
	created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tool_executions (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    tool_name VARCHAR(255) NOT NULL,
    tool_request JSONB,
    tool_response JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() at time zone 'utc')
);