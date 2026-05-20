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
    """Get the OpenF1 session_key for a DB session, with caching."""
    ck = _cache.make_key("openf1_session_key", session_id)
    cached = _cache.get(ck)
    if cached is not None:
        return cached

    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT year, session_key FROM sessions WHERE id = %s", (session_id,))
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return None

    session_key = row.get('session_key')
    if session_key:
        _cache.set(ck, session_key, ttl=_cache.ttl_for_year(row['year']))
    return session_key


def _driver_number(session_id: int, name_acronym: str) -> Optional[str]:
    """Resolve driver abbreviation to driver_number."""
    ck = _cache.make_key("driver_number", session_id, name_acronym)
    cached = _cache.get(ck)
    if cached is not None:
        return cached

    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT driver_number FROM drivers WHERE session_id = %s AND name_acronym = %s LIMIT 1",
                (session_id, name_acronym),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    number = str(row['driver_number']) if row else None
    if number:
        _cache.set(ck, number, ttl=_cache.HISTORICAL_TTL)
    return number


# ---------------------------------------------------------------------------
# DB-backed tools
# ---------------------------------------------------------------------------

@mcp.tool
def get_session_id(event_name: str, year: int, session_name: str = None):
    """Get relevant session id for further tools"""
    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, session_name, location FROM sessions "
                "WHERE LOWER(location) LIKE %s AND year = %s",
                (f"%{event_name.lower()}%", year),
            )
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
def get_fastest_lap_and_sector_comparison(session_id: int, name_acronym: str = None):
    """Get fastest lap and sector times per driver. Pass name_acronym to filter to one driver."""
    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if name_acronym:
                cur.execute("""
                    SELECT name_acronym, lap_number, lap_duration,
                           duration_sector_1, duration_sector_2, duration_sector_3,
                           i1_speed, i2_speed, st_speed, compound
                    FROM laps WHERE session_id = %s AND name_acronym = %s
                    ORDER BY lap_duration ASC NULLS LAST LIMIT 1
                """, (session_id, name_acronym))
            else:
                cur.execute("""
                    SELECT DISTINCT ON (name_acronym)
                        name_acronym, lap_number, lap_duration,
                        duration_sector_1, duration_sector_2, duration_sector_3,
                        i1_speed, i2_speed, st_speed, compound
                    FROM laps WHERE session_id = %s
                    ORDER BY name_acronym, lap_duration ASC NULLS LAST
                """, (session_id,))
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
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT ON (name_acronym)
                    name_acronym, lap_number, st_speed, i1_speed, i2_speed, compound
                FROM laps WHERE session_id = %s AND st_speed IS NOT NULL
                ORDER BY name_acronym, st_speed DESC
            """, (session_id,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Database error in get_top_speed_session: {e}")
        return []
    finally:
        conn.close()


@mcp.tool
def get_driver_results(session_id: int):
    """Get all driver results (position, grid, status, dnf) for a session."""
    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT driver_number, name_acronym, full_name, team_name, team_colour,
                       position, grid_position, dnf, status
                FROM drivers WHERE session_id = %s ORDER BY position NULLS LAST
            """, (session_id,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Database error in get_driver_results: {e}")
        return []
    finally:
        conn.close()


@mcp.tool
def get_laps(session_id: int, name_acronym: str = None):
    """Get lap-by-lap data. Pass name_acronym to filter to one driver."""
    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if name_acronym:
                cur.execute("""
                    SELECT name_acronym, lap_number, lap_duration, date_start,
                           duration_sector_1, duration_sector_2, duration_sector_3,
                           i1_speed, i2_speed, st_speed, is_pit_out_lap,
                           compound, tyre_age_at_start, stint_number, fresh_tyre
                    FROM laps WHERE session_id = %s AND name_acronym = %s
                    ORDER BY lap_number
                """, (session_id, name_acronym))
            else:
                cur.execute("""
                    SELECT name_acronym, lap_number, lap_duration, date_start,
                           duration_sector_1, duration_sector_2, duration_sector_3,
                           i1_speed, i2_speed, st_speed, is_pit_out_lap,
                           compound, tyre_age_at_start, stint_number, fresh_tyre
                    FROM laps WHERE session_id = %s ORDER BY lap_number
                """, (session_id,))
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
            cur.execute("""
                SELECT date, air_temperature, humidity, pressure,
                       rainfall, track_temperature, wind_direction, wind_speed
                FROM weather WHERE session_id = %s ORDER BY date
            """, (session_id,))
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
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT name_acronym, compound, stint_number,
                       COUNT(*) AS laps_on_compound,
                       MIN(lap_number) AS first_lap,
                       MAX(lap_number) AS last_lap,
                       MIN(tyre_age_at_start) AS tyre_age_at_start
                FROM laps WHERE session_id = %s AND compound IS NOT NULL
                GROUP BY name_acronym, compound, stint_number
                ORDER BY name_acronym, first_lap
            """, (session_id,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Database error in get_tyre_strategies: {e}")
        return []
    finally:
        conn.close()


@mcp.tool
def get_weather_impact_laps(session_id: int, name_acronym: str):
    """Get lap-by-lap data with closest weather snapshot for a specific driver."""
    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT l.name_acronym, l.lap_number, l.lap_duration,
                       l.duration_sector_1, l.duration_sector_2, l.duration_sector_3,
                       l.compound, l.date_start,
                       w.air_temperature, w.humidity, w.rainfall,
                       w.track_temperature, w.wind_speed
                FROM laps l
                LEFT JOIN LATERAL (
                    SELECT air_temperature, humidity, rainfall,
                           track_temperature, wind_speed
                    FROM weather w
                    WHERE w.session_id = l.session_id AND w.date <= l.date_start
                    ORDER BY w.date DESC LIMIT 1
                ) w ON true
                WHERE l.session_id = %s AND l.name_acronym = %s
                ORDER BY l.lap_number
            """, (session_id, name_acronym))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Database error in get_weather_impact_laps: {e}")
        return []
    finally:
        conn.close()


@mcp.tool
def get_position_changes(season: int, session_id: int = None, name_acronym: str = None):
    """
    Get position change data.
    - session_id only: all drivers for that race.
    - season + name_acronym: driver's season history.
    - season only: season-wide summary.
    """
    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if session_id is not None:
                cur.execute("""
                    SELECT s.year, s.location, d.driver_number, d.full_name, d.name_acronym,
                           d.team_name, d.grid_position, d.position,
                           (d.grid_position - d.position) AS position_change, d.status, d.dnf
                    FROM drivers d JOIN sessions s ON d.session_id = s.id
                    WHERE d.session_id = %s
                      AND d.position IS NOT NULL AND d.grid_position IS NOT NULL
                    ORDER BY (d.grid_position - d.position) DESC
                """, (session_id,))
            elif name_acronym is not None:
                cur.execute("""
                    SELECT s.location, s.date_start, d.name_acronym, d.full_name,
                           d.team_name, d.grid_position, d.position,
                           (d.grid_position - d.position) AS position_change, d.status
                    FROM drivers d JOIN sessions s ON d.session_id = s.id
                    WHERE s.year = %s AND s.session_name = 'Race'
                      AND d.name_acronym = %s
                      AND d.position IS NOT NULL AND d.grid_position IS NOT NULL
                    ORDER BY s.date_start
                """, (season, name_acronym))
            else:
                cur.execute("""
                    SELECT d.name_acronym, d.full_name, d.team_name,
                           COUNT(*) AS races_counted,
                           SUM(d.grid_position - d.position) AS total_position_change,
                           AVG(d.grid_position - d.position) AS avg_position_change,
                           MAX(d.grid_position - d.position) AS best_single_gain
                    FROM drivers d JOIN sessions s ON d.session_id = s.id
                    WHERE s.year = %s AND s.session_name = 'Race'
                      AND d.position IS NOT NULL AND d.grid_position IS NOT NULL
                    GROUP BY d.name_acronym, d.full_name, d.team_name
                    ORDER BY total_position_change DESC
                """, (season,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("Database error in get_position_changes:\n" + traceback.format_exc())
        return []
    finally:
        conn.close()


@mcp.tool
def get_dnf(season: int, session_id: int = None, name_acronym: str = None):
    """
    Get DNF data.
    - session_id only: DNF drivers in that race.
    - season + name_acronym: driver's DNF history.
    - season only: season-wide DNF stats.
    """
    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if session_id is not None:
                cur.execute("""
                    SELECT s.year, s.location, d.driver_number, d.full_name, d.name_acronym,
                           d.team_name, d.grid_position, d.position, d.status
                    FROM drivers d JOIN sessions s ON d.session_id = s.id
                    WHERE d.session_id = %s AND d.dnf = TRUE
                """, (session_id,))
            elif name_acronym is not None:
                cur.execute("""
                    SELECT s.location, s.date_start, d.name_acronym, d.full_name,
                           d.team_name, d.grid_position, d.position, d.status
                    FROM drivers d JOIN sessions s ON d.session_id = s.id
                    WHERE s.year = %s AND s.session_name = 'Race'
                      AND d.name_acronym = %s AND d.dnf = TRUE
                    ORDER BY s.date_start
                """, (season, name_acronym))
            else:
                cur.execute("""
                    SELECT d.name_acronym, d.full_name, d.team_name,
                           COUNT(*) AS total_races,
                           SUM(CASE WHEN d.dnf THEN 1 ELSE 0 END) AS dnf_count,
                           SUM(CASE WHEN NOT d.dnf THEN 1 ELSE 0 END) AS finished_races
                    FROM drivers d JOIN sessions s ON d.session_id = s.id
                    WHERE s.year = %s AND s.session_name = 'Race'
                    GROUP BY d.name_acronym, d.full_name, d.team_name
                    ORDER BY dnf_count DESC
                """, (season,))
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
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT date, category, message, flag, scope,
                       sector, driver_number, lap_number, qualifying_phase
                FROM race_control WHERE session_id = %s
                ORDER BY date
            """, (session_id,))
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
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT ON (s.location)
                    s.year, s.location, s.session_name, s.date_start,
                    w.air_temperature, w.humidity, w.track_temperature, w.wind_speed
                FROM weather w JOIN sessions s ON w.session_id = s.id
                WHERE w.rainfall = true AND s.year = %s
                ORDER BY s.location, s.date_start
            """, (season,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Database error in get_rainy_sessions: {e}")
        return []
    finally:
        conn.close()


@mcp.tool
def get_pit_stops(session_id: int, name_acronym: str = None):
    """Get pit stop data for a session. Pass name_acronym to filter to one driver."""
    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if name_acronym:
                cur.execute("""
                    SELECT name_acronym, lap_number, stop_duration, lane_duration, date
                    FROM pits WHERE session_id = %s AND name_acronym = %s ORDER BY lap_number
                """, (session_id, name_acronym))
            else:
                cur.execute("""
                    SELECT name_acronym, lap_number, stop_duration, lane_duration, date
                    FROM pits WHERE session_id = %s ORDER BY lap_number
                """, (session_id,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Database error in get_pit_stops: {e}")
        return []
    finally:
        conn.close()


@mcp.tool
def get_overtakes(session_id: int):
    """Get overtake events with driver names for a session."""
    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT o.date, o.position,
                       d1.name_acronym AS overtaking_driver, d1.team_name AS overtaking_team,
                       d2.name_acronym AS overtaken_driver,  d2.team_name AS overtaken_team
                FROM overtakes o
                LEFT JOIN drivers d1 ON d1.session_id = o.session_id
                                     AND d1.driver_number = o.overtaking_driver_number
                LEFT JOIN drivers d2 ON d2.session_id = o.session_id
                                     AND d2.driver_number = o.overtaken_driver_number
                WHERE o.session_id = %s ORDER BY o.date
            """, (session_id,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Database error in get_overtakes: {e}")
        return []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# OpenF1-backed tools (live telemetry)
# ---------------------------------------------------------------------------

@mcp.tool
def get_telemetry(session_id: int, driver_ids: List[str], lap_number: int = None):
    """
    Get car telemetry (speed, throttle, brake, RPM, DRS, gear) from OpenF1.
    Provide driver_ids as name acronyms (e.g. ['HAM', 'VER']).
    Optionally filter to a specific lap_number.
    """
    session_key = _session_openf1_key(session_id)
    if not session_key:
        return {"error": "Could not resolve OpenF1 session key for this session."}

    results = []
    for name_acronym in driver_ids:
        driver_num = _driver_number(session_id, name_acronym)
        if not driver_num:
            continue

        ck = _cache.make_key("telemetry", session_key, driver_num, lap_number or "all")
        cached = _cache.get(ck)
        if cached is not None:
            results.extend(cached)
            continue

        params = {"session_key": session_key, "driver_number": driver_num}

        if lap_number:
            lap_data = openf1.get("laps", {
                "session_key": session_key,
                "driver_number": driver_num,
                "lap_number": lap_number,
            })
            if lap_data:
                lap = lap_data[0]
                date_start   = lap.get("date_start")
                duration_sec = lap.get("lap_duration")
                if date_start and duration_sec:
                    from datetime import datetime, timedelta
                    dt_start = datetime.fromisoformat(date_start.replace("Z", "+00:00"))
                    dt_end   = dt_start + timedelta(seconds=duration_sec)
                    params["date>"] = dt_start.isoformat()
                    params["date<"] = dt_end.isoformat()

        data = openf1.get("car_data", params)
        for point in data:
            point["name_acronym"] = name_acronym

        conn = create_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT year FROM sessions WHERE id = %s", (session_id,))
                row = cur.fetchone()
                ttl = _cache.ttl_for_year(row['year']) if row else _cache.CURRENT_TTL
        finally:
            conn.close()

        _cache.set(ck, data, ttl=ttl)
        results.extend(data)

    return results


@mcp.tool
def get_corner_analysis(session_id: int, name_acronym: str):
    """
    Analyse corner performance using OpenF1 position + car data.
    Returns speed, throttle and brake behaviour with GPS coordinates.
    """
    session_key = _session_openf1_key(session_id)
    if not session_key:
        return {"error": "Could not resolve OpenF1 session key for this session."}

    driver_num = _driver_number(session_id, name_acronym)
    if not driver_num:
        return {"error": f"Driver {name_acronym} not found for session {session_id}."}

    ck = _cache.make_key("corner_analysis", session_key, driver_num)
    cached = _cache.get(ck)
    if cached is not None:
        return cached

    car_data      = openf1.get("car_data", {"session_key": session_key, "driver_number": driver_num})
    location_data = openf1.get("location", {"session_key": session_key, "driver_number": driver_num})

    if not car_data or not location_data:
        return {"error": "No OpenF1 data available for this driver/session."}

    min_len = min(len(car_data), len(location_data))
    merged  = [{**car_data[i], **location_data[i]} for i in range(min_len)]

    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT year FROM sessions WHERE id = %s", (session_id,))
            row = cur.fetchone()
            ttl = _cache.ttl_for_year(row['year']) if row else _cache.CURRENT_TTL
    finally:
        conn.close()

    _cache.set(ck, merged, ttl=ttl)
    return merged


@mcp.tool
def get_intervals(session_id: int, name_acronym: str = None):
    """
    Get gap to leader and interval to car ahead during a race (live from OpenF1).
    Pass name_acronym to filter to one driver.
    """
    session_key = _session_openf1_key(session_id)
    if not session_key:
        return {"error": "Could not resolve OpenF1 session key."}

    params = {"session_key": session_key}
    if name_acronym:
        driver_num = _driver_number(session_id, name_acronym)
        if driver_num:
            params["driver_number"] = driver_num

    ck = _cache.make_key("intervals", session_key, name_acronym or "all")
    cached = _cache.get(ck)
    if cached is not None:
        return cached

    data = openf1.get("intervals", params)

    conn = create_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT year FROM sessions WHERE id = %s", (session_id,))
            row = cur.fetchone()
            ttl = _cache.ttl_for_year(row['year']) if row else _cache.CURRENT_TTL
    finally:
        conn.close()

    _cache.set(ck, data, ttl=ttl)
    return data


@mcp.tool
def get_championship_standings(year: int):
    """Get drivers and teams championship standings for a given year (live from OpenF1)."""
    ck = _cache.make_key("championship", year)
    cached = _cache.get(ck)
    if cached is not None:
        return cached

    drivers_standings = openf1.get("drivers_championship", {"year": year})
    teams_standings   = openf1.get("teams_championship",   {"year": year})

    result = {"drivers": drivers_standings, "teams": teams_standings}
    _cache.set(ck, result, ttl=_cache.ttl_for_year(year))
    return result


if __name__ == "__main__":
    mcp.run()
