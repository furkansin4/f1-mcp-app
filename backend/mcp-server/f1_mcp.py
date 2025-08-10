from fastmcp import FastMCP
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, List, Tuple, Optional
import os
import logging
from dotenv import load_dotenv
import traceback

load_dotenv()

mcp = FastMCP("Formula 1 MCP Server")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_db_connection():
    """Create a new database connection"""
    try:
        connection = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            port=os.getenv('DB_PORT'),
        )
        return connection
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

@mcp.tool
def get_session_id(event_name: str, year: int, session_name: str = None):
    """Get relevant session id for further tools"""
    conn = create_db_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = "SELECT id, session_name, event_name FROM sessions WHERE LOWER(event_name) LIKE %s AND season = %s"
            event_pattern = f"%{event_name.lower()}%"
            cur.execute(query, (event_pattern, year))
            results = cur.fetchall()
            
            # If session_name is provided, filter further
            if session_name:
                filtered_results = [r for r in results if session_name.lower() in r['session_name'].lower()]
                return filtered_results if filtered_results else results
            
            return results
    
    except Exception as e:
        logger.error(f"Database error in get_session_id: {e}")
        return []
    
    finally:
        conn.close()


@mcp.tool
def get_fastest_lap_and_sector_comparison(session_id: int, driver_id: str = None):
    """
    Get fastest lap. 
    
    If `session_id` is provided, returns results for a specific race session.
    If also driver_id is provided, returns driver's fastest lap.
    """
    params = []

    if driver_id:
        query = """
            SELECT
                driver_id,
                lap_number,
                lap_time,
                sector1_time,
                sector2_time,
                sector3_time,
                speed_i1,
                speed_i2,
                speed_fl,
                speed_st,
                compound,
                team
            FROM laps 
            WHERE session_id = %s
            AND driver_id = %s
            ORDER BY lap_time ASC NULLS LAST 
            LIMIT 1
        """
        params = [session_id] + [driver_id]

    else:
        query = """
            SELECT DISTINCT ON (driver_id)
                driver_id,
                lap_number,
                lap_time,
                sector1_time,
                sector2_time,
                sector3_time,
                speed_i1,
                speed_i2,
                speed_fl,
                speed_st,
                compound,
                team
            FROM laps
            WHERE session_id = %s
            ORDER BY driver_id, lap_time ASC NULLS LAST;
        """
        params = [session_id]

    
    conn = create_db_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            results = cur.fetchall()
            
        return [dict(row) for row in results]
    
    except Exception as e:
        logger.error(f"Database error in get_position_changes: {e}")
        return []
    
    finally:
        conn.close()

@mcp.tool
def get_top_speed_session(session_id:int):
    """Get top speed in a session"""
    conn = create_db_connection()

    query = """
            SELECT DISTINCT ON (driver_id)
                driver_id,
                lap_number,
                lap_time,
                sector1_time,
                sector2_time,
                sector3_time,
                speed_i1,
                speed_i2,
                speed_fl,
                speed_st,
                compound,
                team
            FROM laps
            WHERE session_id = %s
            AND speed_st is not null
            ORDER BY driver_id, speed_st DESC

            """
    params = [session_id]

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            results = cur.fetchall()
            
        return [dict(row) for row in results]
    
    except Exception as e:
        logger.error(f"Database error in get_position_changes: {e}")
        return []
    
    finally:
        conn.close()

@mcp.tool
def get_driver_results(session_id: int):
    """Get all driver results for a session"""
    conn = create_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM drivers WHERE session_id = %s ORDER BY position", (session_id,))
            results = cur.fetchall()
        
        return [dict(row) for row in results]
    
    except Exception as e:
        logger.error(f"Database error in get_driver_results: {e}")
        return []
    
    finally:
        conn.close()

@mcp.tool
def get_laps(session_id: int):
    """Get all lap-by-lap data for every driver in a session"""
    conn = create_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM laps WHERE session_id = %s ORDER BY lap_number", (session_id,))
            results = cur.fetchall()
        
        return [dict(row) for row in results]
    
    except Exception as e:
        logger.error(f"Database error in get_driver_results: {e}")
        return []
    
    finally:
        conn.close()


@mcp.tool
def get_weekend_weather(session_id: int):
    """Get weather data for a session"""
    conn = create_db_connection()
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM weather WHERE session_id = %s", (session_id,))
            results = cur.fetchall()
        
        return [dict(row) for row in results]
    
    except Exception as e:
        logger.error(f"Database error in get_weekend_weather: {e}")
        return []
    
    finally:
        conn.close()


@mcp.tool
def get_tyre_strategies(session_id:int):
    """Get tyre strategies by each session"""
    conn = create_db_connection()

    query = """
            SELECT
                driver_id,
                compound,
                team,
                COUNT(*) AS laps_on_compound,
                MIN(lap_number) AS first_lap_on_compound,
                MAX(lap_number) AS last_lap_on_compound
            FROM laps
            WHERE session_id = %s
            AND compound IS NOT NULL
            GROUP BY driver_id, compound, team
            ORDER BY driver_id, first_lap_on_compound;

            """
    params = [session_id]

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            results = cur.fetchall()
            
        return [dict(row) for row in results]
    
    except Exception as e:
        logger.error(f"Database error in get_tyre_strategies: {e}")
        return []
    
    finally:
        conn.close()

@mcp.tool
def get_weather_impact_laps(session_id: int, driver_id: str):
    """Get lap-by-lap data with corresponding weather conditions for a specific driver"""
    conn = create_db_connection()

    query = """
            SELECT 
                l.*,
                w.air_temp,
                w.humidity,
                w.pressure,
                w.rainfall,
                w.track_temp,
                w.wind_direction,
                w.wind_speed,
                w.session_time as weather_session_time
            FROM laps l
            LEFT JOIN LATERAL (
                SELECT air_temp, humidity, pressure, rainfall, track_temp, 
                    wind_direction, wind_speed, session_time
                FROM weather w
                WHERE w.session_id = l.session_id 
                AND w.session_time <= l.session_time
                ORDER BY w.session_time DESC
                LIMIT 1
            ) w ON true
            WHERE session_id = %s
            AND driver_id = %s
            ORDER BY l.session_id, l.driver_id, l.lap_number;
            """
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (session_id, driver_id))
            results = cur.fetchall()
        
        return [dict(row) for row in results]
    
    except Exception as e:
        logger.error(f"Database error in get_weekend_weather: {e}")
        return []
    
    finally:
        conn.close()

@mcp.tool
def get_telemetry(session_id: int, lap_number: int, driver_ids: List[str]):
    """Get telemetry data for specific drivers in a session and lap"""
    # Create placeholders for the IN clause
    placeholders = ','.join(['%s' for _ in driver_ids])
    
    query = f"""
        SELECT *
            FROM telemetry
        WHERE session_id = %s
        AND lap_number = %s
        AND driver_id IN ({placeholders})
        ORDER BY session_time
    """
    conn = create_db_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            params = [session_id, lap_number] + driver_ids

            cur.execute(query, params)
            results = cur.fetchall()
            
        return [dict(row) for row in results]
    
    except Exception as e:
        logger.error(f"Database error in get_session_id: {e}")
        return []
    
    finally:
        conn.close()

@mcp.tool
def get_session_performance_summary(session_id: int):
    """Get average session performance summary with telemetry data including speed, RPM, throttle, brake and DRS usage for all drivers"""
    
    query = """
            SELECT
                t.driver_id,
                t.driver_number,
                t.lap_number,
                l.lap_time,
                l.compound,
                l.tyre_life,
                AVG(t.speed) as avg_speed,
                AVG(t.rpm) as avg_rpm,
                AVG(t.throttle) as avg_throttle,
                AVG(CASE WHEN brake THEN 1 ELSE 0 END) as brake_percentage,
                AVG(CASE WHEN t.drs > 1 THEN 1 ELSE 0 END) as drs_usage
            FROM telemetry t
            LEFT JOIN laps l ON t.session_id = l.session_id 
                AND t.driver_id = l.driver_id 
                AND t.lap_number = l.lap_number
            WHERE t.session_id = %s
            GROUP BY t.driver_id, t.driver_number, t.lap_number, l.lap_time, l.compound, l.tyre_life
            ORDER BY t.driver_id, t.lap_number;
    """
    conn = create_db_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            params = [session_id]

            cur.execute(query, params)
            results = cur.fetchall()
            
        return [dict(row) for row in results]
    
    except Exception as e:
        logger.error(f"Database error in get_session_performance_summary: {e}")
        return []
    
    finally:
        conn.close()


@mcp.tool
def get_position_changes(season: int, session_id: int = None, driver_id: str = None):
    """
    Get F1 driver position change data.

    - If session_id is provided: returns results for a specific race session.
    - If driver_id is provided: returns position changes for that driver across the season.
    - Otherwise: returns season summary of position changes for all drivers.
    """
    params = []
    query = ""

    if session_id is not None:
        query = """
            SELECT
                s.season,
                s.event_name,
                d.driver_number,
                d.full_name,
                d.driver_id,
                d.team_name,
                d.grid_position,
                d.position,
                (d.grid_position - d.position) AS position_change,
                d.points,
                d.status,
                d.dnf
            FROM drivers d
            JOIN sessions s ON d.session_id = s.id
            WHERE d.session_id = %s
              AND s.event_name NOT LIKE 'Pre%%'
              AND d.position IS NOT NULL
              AND d.grid_position IS NOT NULL
            ORDER BY (d.grid_position - d.position) DESC
        """
        params = [session_id]

    elif driver_id is not None:
        query = """
            SELECT 
                s.event_name,
                s.date,
                d.driver_number,
                d.full_name,
                d.driver_id,
                d.team_name,
                d.grid_position,
                d.position,
                (d.grid_position - d.position) AS position_change,
                d.points,
                d.status
            FROM drivers d
            JOIN sessions s ON d.session_id = s.id
            WHERE s.season = %s
              AND s.event_name NOT LIKE 'Pre%%'
              AND d.driver_id = %s
              AND d.position IS NOT NULL
              AND d.grid_position IS NOT NULL
            ORDER BY position_change DESC
        """
        params = [season, driver_id]

    else:
        query = """
            SELECT
                d.driver_number,
                d.full_name,
                d.driver_id,
                d.team_name,
                COUNT(*) AS races_counted,
                SUM(d.grid_position - d.position) AS total_position_change,
                AVG(d.grid_position - d.position) AS avg_position_change,
                SUM(d.points) AS total_points,
                MAX(d.grid_position - d.position) AS best_single_gain
            FROM drivers d
            JOIN sessions s ON d.session_id = s.id
            WHERE s.season = %s
              AND s.event_name NOT LIKE 'Pre%%'
              AND d.position IS NOT NULL
              AND d.grid_position IS NOT NULL
            GROUP BY d.driver_number, d.full_name, d.driver_id, d.team_name
            ORDER BY total_position_change DESC
        """
        params = [season]

    conn = create_db_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            cur.execute(query, params)
            results = cur.fetchall()
            return [dict(row) for row in results]

    except Exception as e:
        logger.error("Database error in get_position_changes:\n" + traceback.format_exc())
        return []

    finally:
        if conn:
            conn.close()


@mcp.tool
def get_dnf(season: int, session_id: int = None, driver_id: str = None):
    """
    Get F1 driver DNF (Did Not Finish) data for a given season.
    If session_id is provided, returns DNF drivers from that session.
    If driver_id is provided, returns DNF records for that driver in the season.
    Otherwise, returns all drivers with DNF statistics for the season.
    """
    params = []
    query = ""

    if session_id is not None:
        query = """
            SELECT
                s.season,
                s.event_name,
                d.driver_number,
                d.full_name,
                d.driver_id,
                d.team_name,
                d.grid_position,
                d.classified_position,
                d.points,
                d.status,
                d.dnf
            FROM drivers d
            JOIN sessions s ON d.session_id = s.id
            WHERE d.session_id = %s
              AND d.dnf = TRUE
              AND d.position IS NOT NULL
              AND d.grid_position IS NOT NULL
            ORDER BY (d.grid_position - d.position) DESC
        """
        params = [session_id]

    elif driver_id is not None:
        query = """
            SELECT
                s.event_name,
                d.driver_number,
                d.full_name,
                d.driver_id,
                d.team_name,
                d.grid_position,
                d.position
            FROM drivers d
            JOIN sessions s ON d.session_id = s.id
            WHERE s.season = %s
              AND s.event_name NOT LIKE 'Pre%%'
              AND d.driver_id = %s
              AND d.dnf = TRUE
              AND d.position IS NOT NULL
              AND d.grid_position IS NOT NULL
        """
        params = [season, driver_id]

    else:
        query = """
            SELECT
                d.driver_number,
                d.full_name,
                d.driver_id,
                d.team_name,
                COUNT(*) AS total_races,
                SUM(CASE WHEN d.dnf = TRUE THEN 1 ELSE 0 END) AS dnf_count,
                SUM(CASE WHEN d.dnf = FALSE THEN 1 ELSE 0 END) AS finished_races
            FROM drivers d
            JOIN sessions s ON d.session_id = s.id
            WHERE s.season = %s
              AND s.event_name NOT LIKE 'Pre%%'
              AND d.position IS NOT NULL
              AND d.grid_position IS NOT NULL
            GROUP BY d.driver_number, d.full_name, d.driver_id, d.team_name
            ORDER BY dnf_count DESC
        """
        params = [season]

    conn = create_db_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            cur.execute(query, params)
            results = cur.fetchall()
            return [dict(row) for row in results]

    except Exception as e:
        logger.error("Database error in get_dnf:\n" + traceback.format_exc())
        return []

    finally:
        conn.close()


@mcp.tool
def get_race_control_messages(session_id:int):
    """Get race control messages by each session"""
    conn = create_db_connection()

    query = """
            SELECT
                l.driver_id,
                l.lap_number,
                r.message,
                r.flag,
                r.lap AS race_control_lap
            FROM laps l
            LEFT JOIN race_control r
                ON r.session_id = l.session_id AND r.lap = l.lap_number
            WHERE l.session_id = %s
            AND r.message is NOT NULL;
            """
    params = [session_id]

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            results = cur.fetchall()
            
        return [dict(row) for row in results]
    
    except Exception as e:
        logger.error(f"Database error in get_position_changes: {e}")
        return []
    
    finally:
        conn.close()


@mcp.tool
def get_rainy_sessions(season: int):
    """Get rainy sessions"""
    conn = create_db_connection()

    query = """
            SELECT DISTINCT ON (s.event_name)
                s.season,
                s.event_name,
                s.session_name,
                s.date,
                w.session_time,
                w.air_temp,
                w.humidity,
                w.pressure,
                w.track_temp,
                w.wind_direction,
                w.wind_speed
            FROM weather w
            JOIN sessions s ON w.session_id = s.id
            WHERE w.rainfall = true
            AND s.season = %s
            ORDER BY s.event_name, s.date, w.session_time;
            """

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (season,))
            results = cur.fetchall()
        
        return [dict(row) for row in results]
    
    except Exception as e:
        logger.error(f"Database error in get_driver_results: {e}")
        return []
    
    finally:
        conn.close()




if __name__ == "__main__":

    mcp.run()