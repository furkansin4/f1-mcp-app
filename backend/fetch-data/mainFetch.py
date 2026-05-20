import os
import logging
import httpx
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('f1_data_fetch.log'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

OPENF1_BASE = "https://api.openf1.org/v1"


def openf1_get(endpoint: str, params: dict) -> list:
    with httpx.Client(timeout=60.0) as client:
        response = client.get(
            f"{OPENF1_BASE}/{endpoint}",
            params={k: v for k, v in params.items() if v is not None},
        )
        response.raise_for_status()
        return response.json()


def seconds_to_interval(value) -> str | None:
    """Convert a float (seconds) to a PostgreSQL-compatible interval string."""
    if value is None:
        return None
    return f"{float(value)} seconds"


class OpenF1Pipeline:
    def __init__(self):
        user     = os.getenv('DB_USER', 'postgres')
        password = os.getenv('DB_PASSWORD', '')
        host     = os.getenv('DB_HOST', 'localhost')
        port     = os.getenv('DB_PORT', '5432')
        database = os.getenv('DB_NAME', 'f1_db')
        self.engine = create_engine(
            f"postgresql://{user}:{password}@{host}:{port}/{database}",
            pool_pre_ping=True,
        )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def fetch_year(self, year: int, session_types: list[str] | None = None):
        if session_types is None:
            session_types = ['Qualifying', 'Race']

        sessions = openf1_get("sessions", {"year": year})
        for session in sessions:
            if session.get('session_name') not in session_types:
                continue
            self._process_session(session, year)

    # ------------------------------------------------------------------
    # Per-session orchestration
    # ------------------------------------------------------------------

    def _process_session(self, session: dict, year: int):
        location     = session.get('location', 'Unknown')
        session_name = session.get('session_name', '')
        session_key  = session.get('session_key')

        logger.info(f"Processing {year} {location} {session_name} (key={session_key})")
        try:
            session_id = self._store_session(session, year)
            driver_map = self._store_drivers(session_key, session_id)
            self._store_laps(session_key, session_id, driver_map)
            self._store_weather(session_key, session_id)
            self._store_race_control(session_key, session_id)
            if session_name == 'Race':
                self._store_race_results(session_key, session_id, driver_map)
            elif session_name == 'Qualifying':
                self._store_qualifying_results(session_id)
            logger.info(f"✓ {year} {location} {session_name}")
        except Exception as e:
            logger.error(f"✗ {year} {location} {session_name}: {e}")

    # ------------------------------------------------------------------
    # Storage helpers
    # ------------------------------------------------------------------

    def _store_session(self, session: dict, year: int) -> int:
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                INSERT INTO sessions (season, event_name, session_name, date, openf1_session_key)
                VALUES (:season, :event_name, :session_name, :date, :openf1_session_key)
                ON CONFLICT (season, event_name, session_name)
                DO UPDATE SET openf1_session_key = EXCLUDED.openf1_session_key
                RETURNING id
            """), {
                'season':              year,
                'event_name':          session.get('location'),
                'session_name':        session.get('session_name'),
                'date':                session.get('date_start'),
                'openf1_session_key':  session.get('session_key'),
            })
            session_id = result.fetchone()[0]
            conn.commit()
        return session_id

    def _store_drivers(self, session_key: int, session_id: int) -> dict[int, str]:
        """Store drivers and return {driver_number: abbreviation} map."""
        drivers = openf1_get("drivers", {"session_key": session_key})
        driver_map: dict[int, str] = {}

        with self.engine.connect() as conn:
            for d in drivers:
                num   = d.get('driver_number')
                abbr  = d.get('name_acronym', str(num))
                driver_map[num] = abbr

                conn.execute(text("""
                    INSERT INTO drivers (
                        session_id, driver_number, broadcast_name, full_name,
                        driver_id, team_name, team_color,
                        first_name, last_name, headshot_url, country_code
                    ) VALUES (
                        :session_id, :driver_number, :broadcast_name, :full_name,
                        :driver_id, :team_name, :team_color,
                        :first_name, :last_name, :headshot_url, :country_code
                    )
                    ON CONFLICT (session_id, driver_number) DO NOTHING
                """), {
                    'session_id':     session_id,
                    'driver_number':  str(num),
                    'broadcast_name': d.get('broadcast_name'),
                    'full_name':      d.get('full_name'),
                    'driver_id':      abbr,
                    'team_name':      d.get('team_name'),
                    'team_color':     d.get('team_colour'),
                    'first_name':     d.get('first_name'),
                    'last_name':      d.get('last_name'),
                    'headshot_url':   d.get('headshot_url'),
                    'country_code':   d.get('country_code'),
                })
            conn.commit()

        logger.info(f"  Stored {len(drivers)} drivers")
        return driver_map

    def _store_laps(self, session_key: int, session_id: int, driver_map: dict[int, str]):
        laps   = openf1_get("laps",   {"session_key": session_key})
        stints = openf1_get("stints", {"session_key": session_key})

        # Build stint lookup: (driver_number, lap_number) → {compound, tyre_life, stint}
        stint_lookup: dict[tuple, dict] = {}
        for s in stints:
            for lap_no in range(s.get('lap_start', 0), s.get('lap_end', 0) + 1):
                key = (s.get('driver_number'), lap_no)
                stint_lookup[key] = {
                    'compound':   s.get('compound'),
                    'tyre_life':  lap_no - s.get('lap_start', 0) + 1,
                    'stint':      s.get('stint_number'),
                    'fresh_tyre': s.get('lap_start') == lap_no,
                }

        with self.engine.connect() as conn:
            for lap in laps:
                num      = lap.get('driver_number')
                lap_no   = lap.get('lap_number')
                stint    = stint_lookup.get((num, lap_no), {})
                driver_id = driver_map.get(num, str(num))

                conn.execute(text("""
                    INSERT INTO laps (
                        session_id, driver_id, lap_number,
                        lap_time, sector1_time, sector2_time, sector3_time,
                        speed_i1, speed_i2, speed_st,
                        compound, tyre_life, fresh_tyre, stint,
                        is_personal_best
                    ) VALUES (
                        :session_id, :driver_id, :lap_number,
                        :lap_time, :sector1_time, :sector2_time, :sector3_time,
                        :speed_i1, :speed_i2, :speed_st,
                        :compound, :tyre_life, :fresh_tyre, :stint,
                        :is_personal_best
                    )
                """), {
                    'session_id':     session_id,
                    'driver_id':      driver_id,
                    'lap_number':     lap_no,
                    'lap_time':       seconds_to_interval(lap.get('lap_duration')),
                    'sector1_time':   seconds_to_interval(lap.get('duration_sector_1')),
                    'sector2_time':   seconds_to_interval(lap.get('duration_sector_2')),
                    'sector3_time':   seconds_to_interval(lap.get('duration_sector_3')),
                    'speed_i1':       lap.get('i1_speed'),
                    'speed_i2':       lap.get('i2_speed'),
                    'speed_st':       lap.get('st_speed'),
                    'compound':       stint.get('compound'),
                    'tyre_life':      stint.get('tyre_life'),
                    'fresh_tyre':     stint.get('fresh_tyre'),
                    'stint':          stint.get('stint'),
                    'is_personal_best': lap.get('is_pit_out_lap') is False and lap.get('lap_duration') is not None,
                })
            conn.commit()

        logger.info(f"  Stored {len(laps)} laps")

    def _store_weather(self, session_key: int, session_id: int):
        weather = openf1_get("weather", {"session_key": session_key})

        with self.engine.connect() as conn:
            for w in weather:
                conn.execute(text("""
                    INSERT INTO weather (
                        session_id, air_temp, humidity, pressure,
                        rainfall, track_temp, wind_direction, wind_speed
                    ) VALUES (
                        :session_id, :air_temp, :humidity, :pressure,
                        :rainfall, :track_temp, :wind_direction, :wind_speed
                    )
                """), {
                    'session_id':    session_id,
                    'air_temp':      w.get('air_temperature'),
                    'humidity':      w.get('humidity'),
                    'pressure':      w.get('pressure'),
                    'rainfall':      bool(w.get('rainfall')),
                    'track_temp':    w.get('track_temperature'),
                    'wind_direction': w.get('wind_direction'),
                    'wind_speed':    w.get('wind_speed'),
                })
            conn.commit()

        logger.info(f"  Stored {len(weather)} weather records")

    def _store_race_control(self, session_key: int, session_id: int):
        messages = openf1_get("race_control", {"session_key": session_key})

        with self.engine.connect() as conn:
            for msg in messages:
                conn.execute(text("""
                    INSERT INTO race_control (
                        session_id, category, message, flag,
                        scope, sector, racing_number, lap
                    ) VALUES (
                        :session_id, :category, :message, :flag,
                        :scope, :sector, :racing_number, :lap
                    )
                """), {
                    'session_id':    session_id,
                    'category':      msg.get('category'),
                    'message':       msg.get('message'),
                    'flag':          msg.get('flag'),
                    'scope':         msg.get('scope'),
                    'sector':        str(msg.get('sector')) if msg.get('sector') else None,
                    'racing_number': str(msg.get('driver_number')) if msg.get('driver_number') else None,
                    'lap':           msg.get('lap_number'),
                })
            conn.commit()

        logger.info(f"  Stored {len(messages)} race control messages")

    def _store_race_results(self, session_key: int, session_id: int, driver_map: dict[int, str]):
        """Derive final position, grid position and DNF from OpenF1 /position."""
        positions = openf1_get("position", {"session_key": session_key})
        if not positions:
            logger.warning("  No position data from OpenF1, skipping race results")
            return

        first_pos: dict[int, int] = {}
        last_pos: dict[int, int] = {}
        for p in positions:
            num = p.get('driver_number')
            pos = p.get('position')
            if num is None or pos is None:
                continue
            if num not in first_pos:
                first_pos[num] = pos
            last_pos[num] = pos

        with self.engine.connect() as conn:
            max_laps = conn.execute(text(
                "SELECT MAX(lap_number) FROM laps WHERE session_id = :sid"
            ), {"sid": session_id}).scalar() or 0

            driver_lap_counts = {
                row.driver_id: row.laps
                for row in conn.execute(text(
                    "SELECT driver_id, MAX(lap_number) AS laps FROM laps "
                    "WHERE session_id = :sid GROUP BY driver_id"
                ), {"sid": session_id})
            }

            for driver_num, final_pos in last_pos.items():
                driver_id = driver_map.get(driver_num, str(driver_num))
                grid_pos  = first_pos.get(driver_num)
                lap_count = driver_lap_counts.get(driver_id, 0)
                dnf       = bool(lap_count < (max_laps - 3))
                status    = 'DNF' if dnf else 'Finished'

                conn.execute(text("""
                    UPDATE drivers SET
                        position      = :pos,
                        grid_position = :grid,
                        dnf           = :dnf,
                        status        = :status
                    WHERE session_id = :session_id AND driver_id = :driver_id
                """), {
                    'pos': final_pos, 'grid': grid_pos,
                    'dnf': dnf, 'status': status,
                    'session_id': session_id, 'driver_id': driver_id,
                })
            conn.commit()

        logger.info(f"  Updated race results for {len(last_pos)} drivers")

    def _store_qualifying_results(self, session_id: int):
        """Rank drivers by best lap time already in DB and store as qualifying position."""
        with self.engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT driver_id, MIN(lap_time) AS best_time
                FROM laps WHERE session_id = :sid AND lap_time IS NOT NULL
                GROUP BY driver_id
                ORDER BY best_time ASC
            """), {"sid": session_id}).fetchall()

            for rank, row in enumerate(rows, start=1):
                conn.execute(text("""
                    UPDATE drivers SET position = :pos
                    WHERE session_id = :session_id AND driver_id = :driver_id
                """), {'pos': rank, 'session_id': session_id, 'driver_id': row.driver_id})
            conn.commit()

        logger.info(f"  Updated qualifying positions for {len(rows)} drivers")


if __name__ == "__main__":
    pipeline = OpenF1Pipeline()

    years         = [2024, 2025]
    session_types = ['Qualifying', 'Race']

    for year in years:
        logger.info(f"=== Fetching {year} season ===")
        pipeline.fetch_year(year, session_types)

    print("Fetch complete!")
