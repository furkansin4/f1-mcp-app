import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "services"))

import openf1
import cache as _cache

from fastmcp import FastMCP
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Optional
import logging
from dotenv import load_dotenv
import traceback

load_dotenv()

mcp = FastMCP("Formula 1 MCP Server")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD', ''),
        port=os.getenv('DB_PORT', '5432'),
    )


def _session_openf1_key(session_id: int) -> Optional[int]:
    """Get the OpenF1 session_key for a DB session_id, with caching."""
    ck = _cache.make_key("openf1_session_key", session_id)
    cached = _cache.get(ck)
    if cached is not None:
        return cached

    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT season, event_name, session_name FROM sessions WHERE id = %s", (session_id,))
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return None

    session_key = openf1.get_session_key(row['season'], row['event_name'], row['session_name'])
    if session_key:
        _cache.set(ck, session_key, ttl=_cache.ttl_for_year(row['season']))
    return session_key


def _driver_number(session_id: int, driver_id: str) -> Optional[str]:
    """Resolve driver abbreviation to driver_number from the DB."""
    ck = _cache.make_key("driver_number", session_id, driver_id)
    cached = _cache.get(ck)
    if cached is not None:
        return cached

    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT driver_number FROM drivers WHERE session_id = %s AND driver_id = %s LIMIT 1",
                (session_id, driver_id),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    number = row['driver_number'] if row else None
    if number:
        _cache.set(ck, number, ttl=_cache.HISTORICAL_TTL)
    return number


# ---------------------------------------------------------------------------
# DB-backed tools (non-telemetry)
# ---------------------------------------------------------------------------

@mcp.tool
def get_session_id(event_name: str, year: int, session_name: str = None):
    """Get relevant session id for further tools"""
    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = "SELECT id, session_name, event_name FROM sessions WHERE LOWER(event_name) LIKE %s AND season = %s"
            cur.execute(query, (f"%{event_name.lower()}%", year))
            results = cur.fetchall()
            if session_name:
                filtered = [r for r in results if session_name.lower() in r['session_name'].lower()]
                return filtered if filtered else results
            return results
    except Exception as e:
        logger.error(f"Database error in get_session_id: {e}")
        return []
    finally:
        conn.close()


@mcp.tool
def get_fastest_lap_and_sector_comparison(session_id: int, driver_id: str = None):
    """Get fastest lap and sector times. Pass driver_id to get a single driver's fastest lap."""
    params = []
    if driver_id:
        query = """
            SELECT driver_id, lap_number, lap_time, sector1_time, sector2_time, sector3_time,
                   speed_i1, speed_i2, speed_fl, speed_st, compound, team
            FROM laps WHERE session_id = %s AND driver_id = %s
            ORDER BY lap_time ASC NULLS LAST LIMIT 1
        """
        params = [session_id, driver_id]
    else:
        query = """
            SELECT DISTINCT ON (driver_id)
                driver_id, lap_number, lap_time, sector1_time, sector2_time, sector3_time,
                speed_i1, speed_i2, speed_fl, speed_st, compound, team
            FROM laps WHERE session_id = %s
            ORDER BY driver_id, lap_time ASC NULLS LAST
        """
        params = [session_id]

    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Database error in get_fastest_lap_and_sector_comparison: {e}")
        return []
    finally:
        conn.close()


@mcp.tool
def get_top_speed_session(session_id: int):
    """Get each driver's highest recorded straight-line speed in a session."""
    conn = create_db_connection()
    query = """
        SELECT DISTINCT ON (driver_id)
            driver_id, lap_number, lap_time, sector1_time, sector2_time, sector3_time,
            speed_i1, speed_i2, speed_fl, speed_st, compound, team
        FROM laps WHERE session_id = %s AND speed_st IS NOT NULL
        ORDER BY driver_id, speed_st DESC
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, [session_id])
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Database error in get_top_speed_session: {e}")
        return []
    finally:
        conn.close()


@mcp.tool
def get_driver_results(session_id: int):
    """Get all driver results (position, points, status) for a session."""
    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM drivers WHERE session_id = %s ORDER BY position", (session_id,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Database error in get_driver_results: {e}")
        return []
    finally:
        conn.close()


@mcp.tool
def get_laps(session_id: int):
    """Get lap-by-lap data for every driver in a session."""
    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM laps WHERE session_id = %s ORDER BY lap_number", (session_id,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Database error in get_laps: {e}")
        return []
    finally:
        conn.close()


@mcp.tool
def get_weekend_weather(session_id: int):
    """Get weather data for a session."""
    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM weather WHERE session_id = %s", (session_id,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Database error in get_weekend_weather: {e}")
        return []
    finally:
        conn.close()


@mcp.tool
def get_tyre_strategies(session_id: int):
    """Get tyre compound usage per driver in a session."""
    conn = create_db_connection()
    query = """
        SELECT driver_id, compound, team,
               COUNT(*) AS laps_on_compound,
               MIN(lap_number) AS first_lap_on_compound,
               MAX(lap_number) AS last_lap_on_compound
        FROM laps WHERE session_id = %s AND compound IS NOT NULL
        GROUP BY driver_id, compound, team
        ORDER BY driver_id, first_lap_on_compound
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, [session_id])
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Database error in get_tyre_strategies: {e}")
        return []
    finally:
        conn.close()


@mcp.tool
def get_weather_impact_laps(session_id: int, driver_id: str):
    """Get lap-by-lap data with closest weather snapshot for a specific driver."""
    conn = create_db_connection()
    query = """
        SELECT l.*,
               w.air_temp, w.humidity, w.pressure, w.rainfall,
               w.track_temp, w.wind_direction, w.wind_speed,
               w.session_time AS weather_session_time
        FROM laps l
        LEFT JOIN LATERAL (
            SELECT air_temp, humidity, pressure, rainfall, track_temp,
                   wind_direction, wind_speed, session_time
            FROM weather w
            WHERE w.session_id = l.session_id AND w.session_time <= l.session_time
            ORDER BY w.session_time DESC LIMIT 1
        ) w ON true
        WHERE l.session_id = %s AND l.driver_id = %s
        ORDER BY l.lap_number
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (session_id, driver_id))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Database error in get_weather_impact_laps: {e}")
        return []
    finally:
        conn.close()


@mcp.tool
def get_position_changes(season: int, session_id: int = None, driver_id: str = None):
    """
    Get position change data.
    - session_id only: all drivers for that race.
    - season + driver_id: driver's season history.
    - season only: season-wide summary for all drivers.
    """
    conn = create_db_connection()
    params = []

    if session_id is not None:
        query = """
            SELECT s.season, s.event_name, d.driver_number, d.full_name, d.driver_id,
                   d.team_name, d.grid_position, d.position,
                   (d.grid_position - d.position) AS position_change, d.points, d.status, d.dnf
            FROM drivers d JOIN sessions s ON d.session_id = s.id
            WHERE d.session_id = %s AND s.event_name NOT LIKE 'Pre%%'
              AND d.position IS NOT NULL AND d.grid_position IS NOT NULL
            ORDER BY (d.grid_position - d.position) DESC
        """
        params = [session_id]
    elif driver_id is not None:
        query = """
            SELECT s.event_name, s.date, d.driver_number, d.full_name, d.driver_id,
                   d.team_name, d.grid_position, d.position,
                   (d.grid_position - d.position) AS position_change, d.points, d.status
            FROM drivers d JOIN sessions s ON d.session_id = s.id
            WHERE s.season = %s AND s.event_name NOT LIKE 'Pre%%'
              AND d.driver_id = %s AND d.position IS NOT NULL AND d.grid_position IS NOT NULL
            ORDER BY position_change DESC
        """
        params = [season, driver_id]
    else:
        query = """
            SELECT d.driver_number, d.full_name, d.driver_id, d.team_name,
                   COUNT(*) AS races_counted,
                   SUM(d.grid_position - d.position) AS total_position_change,
                   AVG(d.grid_position - d.position) AS avg_position_change,
                   SUM(d.points) AS total_points,
                   MAX(d.grid_position - d.position) AS best_single_gain
            FROM drivers d JOIN sessions s ON d.session_id = s.id
            WHERE s.season = %s AND s.event_name NOT LIKE 'Pre%%'
              AND d.position IS NOT NULL AND d.grid_position IS NOT NULL
            GROUP BY d.driver_number, d.full_name, d.driver_id, d.team_name
            ORDER BY total_position_change DESC
        """
        params = [season]

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("Database error in get_position_changes:\n" + traceback.format_exc())
        return []
    finally:
        conn.close()


@mcp.tool
def get_dnf(season: int, session_id: int = None, driver_id: str = None):
    """
    Get DNF data.
    - session_id only: DNF drivers in that race.
    - season + driver_id: driver's DNF history.
    - season only: season-wide DNF stats for all drivers.
    """
    conn = create_db_connection()
    params = []

    if session_id is not None:
        query = """
            SELECT s.season, s.event_name, d.driver_number, d.full_name, d.driver_id,
                   d.team_name, d.grid_position, d.classified_position, d.points, d.status, d.dnf
            FROM drivers d JOIN sessions s ON d.session_id = s.id
            WHERE d.session_id = %s AND d.dnf = TRUE
        """
        params = [session_id]
    elif driver_id is not None:
        query = """
            SELECT s.event_name, d.driver_number, d.full_name, d.driver_id,
                   d.team_name, d.grid_position, d.position
            FROM drivers d JOIN sessions s ON d.session_id = s.id
            WHERE s.season = %s AND s.event_name NOT LIKE 'Pre%%'
              AND d.driver_id = %s AND d.dnf = TRUE
        """
        params = [season, driver_id]
    else:
        query = """
            SELECT d.driver_number, d.full_name, d.driver_id, d.team_name,
                   COUNT(*) AS total_races,
                   SUM(CASE WHEN d.dnf = TRUE THEN 1 ELSE 0 END) AS dnf_count,
                   SUM(CASE WHEN d.dnf = FALSE THEN 1 ELSE 0 END) AS finished_races
            FROM drivers d JOIN sessions s ON d.session_id = s.id
            WHERE s.season = %s AND s.event_name NOT LIKE 'Pre%%'
            GROUP BY d.driver_number, d.full_name, d.driver_id, d.team_name
            ORDER BY dnf_count DESC
        """
        params = [season]

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("Database error in get_dnf:\n" + traceback.format_exc())
        return []
    finally:
        conn.close()


@mcp.tool
def get_race_control_messages(session_id: int):
    """Get race control messages (flags, safety car, etc.) for a session."""
    conn = create_db_connection()
    query = """
        SELECT l.driver_id, l.lap_number, r.message, r.flag, r.lap AS race_control_lap
        FROM laps l
        LEFT JOIN race_control r ON r.session_id = l.session_id AND r.lap = l.lap_number
        WHERE l.session_id = %s AND r.message IS NOT NULL
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, [session_id])
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Database error in get_race_control_messages: {e}")
        return []
    finally:
        conn.close()


@mcp.tool
def get_rainy_sessions(season: int):
    """Get sessions where rainfall was recorded."""
    conn = create_db_connection()
    query = """
        SELECT DISTINCT ON (s.event_name)
            s.season, s.event_name, s.session_name, s.date,
            w.air_temp, w.humidity, w.track_temp, w.wind_speed
        FROM weather w
        JOIN sessions s ON w.session_id = s.id
        WHERE w.rainfall = true AND s.season = %s
        ORDER BY s.event_name, s.date, w.session_time
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (season,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Database error in get_rainy_sessions: {e}")
        return []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# OpenF1-backed tools (telemetry)
# ---------------------------------------------------------------------------

@mcp.tool
def get_telemetry(session_id: int, driver_ids: List[str], lap_number: int = None):
    """
    Get car telemetry (speed, throttle, brake, RPM, DRS, gear) from OpenF1.
    Provide driver_ids as abbreviations (e.g. ['HAM', 'VER']).
    Optionally filter to a specific lap_number.
    """
    session_key = _session_openf1_key(session_id)
    if not session_key:
        return {"error": "Could not resolve OpenF1 session key for this session."}

    results = []
    for driver_id in driver_ids:
        driver_number = _driver_number(session_id, driver_id)
        if not driver_number:
            continue

        ck = _cache.make_key("telemetry", session_key, driver_number, lap_number or "all")
        cached = _cache.get(ck)
        if cached is not None:
            results.extend(cached)
            continue

        params = {"session_key": session_key, "driver_number": driver_number}

        if lap_number:
            # Get lap timing to slice telemetry by date range
            lap_data = openf1.get("laps", {
                "session_key": session_key,
                "driver_number": driver_number,
                "lap_number": lap_number,
            })
            if lap_data:
                lap = lap_data[0]
                date_start = lap.get("date_start")
                duration_ms = lap.get("lap_duration")
                if date_start and duration_ms:
                    from datetime import datetime, timedelta, timezone
                    dt_start = datetime.fromisoformat(date_start.replace("Z", "+00:00"))
                    dt_end = dt_start + timedelta(seconds=duration_ms)
                    params["date>"] = dt_start.isoformat()
                    params["date<"] = dt_end.isoformat()

        data = openf1.get("car_data", params)

        # Annotate with driver_id for consistency
        for point in data:
            point["driver_id"] = driver_id

        # Determine TTL from the session year
        conn = create_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT season FROM sessions WHERE id = %s", (session_id,))
                row = cur.fetchone()
                ttl = _cache.ttl_for_year(row['season']) if row else _cache.CURRENT_TTL
        finally:
            conn.close()

        _cache.set(ck, data, ttl=ttl)
        results.extend(data)

    return results


@mcp.tool
def get_corner_analysis(session_id: int, driver_id: str):
    """
    Analyse corner performance for a driver using OpenF1 position + car data.
    Returns speed, throttle and brake behaviour near each corner.
    """
    session_key = _session_openf1_key(session_id)
    if not session_key:
        return {"error": "Could not resolve OpenF1 session key for this session."}

    driver_number = _driver_number(session_id, driver_id)
    if not driver_number:
        return {"error": f"Driver {driver_id} not found for session {session_id}."}

    ck = _cache.make_key("corner_analysis", session_key, driver_number)
    cached = _cache.get(ck)
    if cached is not None:
        return cached

    car_data = openf1.get("car_data", {"session_key": session_key, "driver_number": driver_number})
    location_data = openf1.get("location", {"session_key": session_key, "driver_number": driver_number})

    if not car_data or not location_data:
        return {"error": "No OpenF1 data available for this driver/session."}

    # Merge car_data and location by closest date
    # Both are time-series; zip by index (same sample rate from OpenF1)
    merged = []
    min_len = min(len(car_data), len(location_data))
    for i in range(min_len):
        point = {**car_data[i], **location_data[i]}
        merged.append(point)

    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT season FROM sessions WHERE id = %s",
                (session_id,),
            )
            row = cur.fetchone()
            ttl = _cache.ttl_for_year(row['season']) if row else _cache.CURRENT_TTL
    finally:
        conn.close()

    _cache.set(ck, merged, ttl=ttl)
    return merged


if __name__ == "__main__":
    mcp.run()
