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
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return response.json()


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
                self._store_race_results(session_key, session_id)
                self._store_pits(session_key, session_id, driver_map)
                self._store_overtakes(session_key, session_id)
            elif session_name == 'Qualifying':
                self._store_qualifying_results(session_key, session_id)
            logger.info(f"✓ {year} {location} {session_name}")
        except Exception as e:
            logger.error(f"✗ {year} {location} {session_name}: {e}")

    # ------------------------------------------------------------------
    # Storage helpers
    # ------------------------------------------------------------------

    def _store_session(self, session: dict, year: int) -> int:
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                INSERT INTO sessions (
                    session_key, meeting_key, year, location,
                    country_name, country_code, circuit_short_name,
                    session_name, session_type, date_start, date_end, gmt_offset
                ) VALUES (
                    :session_key, :meeting_key, :year, :location,
                    :country_name, :country_code, :circuit_short_name,
                    :session_name, :session_type, :date_start, :date_end, :gmt_offset
                )
                ON CONFLICT (session_key)
                DO UPDATE SET
                    meeting_key = EXCLUDED.meeting_key,
                    date_start  = EXCLUDED.date_start,
                    date_end    = EXCLUDED.date_end
                RETURNING id
            """), {
                'session_key':        session.get('session_key'),
                'meeting_key':        session.get('meeting_key'),
                'year':               year,
                'location':           session.get('location'),
                'country_name':       session.get('country_name'),
                'country_code':       session.get('country_code'),
                'circuit_short_name': session.get('circuit_short_name'),
                'session_name':       session.get('session_name'),
                'session_type':       session.get('session_type'),
                'date_start':         session.get('date_start'),
                'date_end':           session.get('date_end'),
                'gmt_offset':         session.get('gmt_offset'),
            })
            session_id = result.fetchone()[0]
            conn.commit()
        return session_id

    def _store_drivers(self, session_key: int, session_id: int) -> dict[int, str]:
        """Store drivers and return {driver_number: name_acronym} map."""
        drivers = openf1_get("drivers", {"session_key": session_key})
        driver_map: dict[int, str] = {}

        with self.engine.connect() as conn:
            for d in drivers:
                num  = d.get('driver_number')
                abbr = d.get('name_acronym', str(num))
                driver_map[num] = abbr

                conn.execute(text("""
                    INSERT INTO drivers (
                        session_id, driver_number, name_acronym,
                        broadcast_name, full_name, first_name, last_name,
                        team_name, team_colour, headshot_url, country_code
                    ) VALUES (
                        :session_id, :driver_number, :name_acronym,
                        :broadcast_name, :full_name, :first_name, :last_name,
                        :team_name, :team_colour, :headshot_url, :country_code
                    )
                    ON CONFLICT (session_id, driver_number) DO NOTHING
                """), {
                    'session_id':     session_id,
                    'driver_number':  num,
                    'name_acronym':   abbr,
                    'broadcast_name': d.get('broadcast_name'),
                    'full_name':      d.get('full_name'),
                    'first_name':     d.get('first_name'),
                    'last_name':      d.get('last_name'),
                    'team_name':      d.get('team_name'),
                    'team_colour':    d.get('team_colour'),
                    'headshot_url':   d.get('headshot_url'),
                    'country_code':   d.get('country_code'),
                })
            conn.commit()

        logger.info(f"  Stored {len(drivers)} drivers")
        return driver_map

    def _store_laps(self, session_key: int, session_id: int, driver_map: dict[int, str]):
        laps   = openf1_get("laps",   {"session_key": session_key})
        stints = openf1_get("stints", {"session_key": session_key})

        stint_lookup: dict[tuple, dict] = {}
        for s in stints:
            lap_start = s.get('lap_start', 0)
            lap_end   = s.get('lap_end', 0)
            for lap_no in range(lap_start, lap_end + 1):
                stint_lookup[(s.get('driver_number'), lap_no)] = {
                    'compound':          s.get('compound'),
                    'tyre_age_at_start': s.get('tyre_age_at_start'),
                    'stint_number':      s.get('stint_number'),
                    'fresh_tyre':        s.get('tyre_age_at_start') == 0 and lap_no == lap_start,
                }

        with self.engine.connect() as conn:
            for lap in laps:
                num    = lap.get('driver_number')
                lap_no = lap.get('lap_number')
                stint  = stint_lookup.get((num, lap_no), {})

                conn.execute(text("""
                    INSERT INTO laps (
                        session_id, driver_number, name_acronym, lap_number,
                        lap_duration, date_start,
                        duration_sector_1, duration_sector_2, duration_sector_3,
                        i1_speed, i2_speed, st_speed, is_pit_out_lap,
                        compound, tyre_age_at_start, stint_number, fresh_tyre
                    ) VALUES (
                        :session_id, :driver_number, :name_acronym, :lap_number,
                        :lap_duration, :date_start,
                        :duration_sector_1, :duration_sector_2, :duration_sector_3,
                        :i1_speed, :i2_speed, :st_speed, :is_pit_out_lap,
                        :compound, :tyre_age_at_start, :stint_number, :fresh_tyre
                    )
                """), {
                    'session_id':        session_id,
                    'driver_number':     num,
                    'name_acronym':      driver_map.get(num, str(num)),
                    'lap_number':        lap_no,
                    'lap_duration':      lap.get('lap_duration'),
                    'date_start':        lap.get('date_start'),
                    'duration_sector_1': lap.get('duration_sector_1'),
                    'duration_sector_2': lap.get('duration_sector_2'),
                    'duration_sector_3': lap.get('duration_sector_3'),
                    'i1_speed':          lap.get('i1_speed'),
                    'i2_speed':          lap.get('i2_speed'),
                    'st_speed':          lap.get('st_speed'),
                    'is_pit_out_lap':    lap.get('is_pit_out_lap'),
                    'compound':          stint.get('compound'),
                    'tyre_age_at_start': stint.get('tyre_age_at_start'),
                    'stint_number':      stint.get('stint_number'),
                    'fresh_tyre':        stint.get('fresh_tyre'),
                })
            conn.commit()

        logger.info(f"  Stored {len(laps)} laps")

    def _store_weather(self, session_key: int, session_id: int):
        weather = openf1_get("weather", {"session_key": session_key})

        with self.engine.connect() as conn:
            for w in weather:
                conn.execute(text("""
                    INSERT INTO weather (
                        session_id, date, air_temperature, humidity, pressure,
                        rainfall, track_temperature, wind_direction, wind_speed
                    ) VALUES (
                        :session_id, :date, :air_temperature, :humidity, :pressure,
                        :rainfall, :track_temperature, :wind_direction, :wind_speed
                    )
                """), {
                    'session_id':        session_id,
                    'date':              w.get('date'),
                    'air_temperature':   w.get('air_temperature'),
                    'humidity':          w.get('humidity'),
                    'pressure':          w.get('pressure'),
                    'rainfall':          bool(w.get('rainfall')),
                    'track_temperature': w.get('track_temperature'),
                    'wind_direction':    w.get('wind_direction'),
                    'wind_speed':        w.get('wind_speed'),
                })
            conn.commit()

        logger.info(f"  Stored {len(weather)} weather records")

    def _store_race_control(self, session_key: int, session_id: int):
        messages = openf1_get("race_control", {"session_key": session_key})

        with self.engine.connect() as conn:
            for msg in messages:
                conn.execute(text("""
                    INSERT INTO race_control (
                        session_id, date, category, message, flag,
                        scope, sector, driver_number, lap_number, qualifying_phase
                    ) VALUES (
                        :session_id, :date, :category, :message, :flag,
                        :scope, :sector, :driver_number, :lap_number, :qualifying_phase
                    )
                """), {
                    'session_id':       session_id,
                    'date':             msg.get('date'),
                    'category':         msg.get('category'),
                    'message':          msg.get('message'),
                    'flag':             msg.get('flag'),
                    'scope':            msg.get('scope'),
                    'sector':           msg.get('sector'),
                    'driver_number':    msg.get('driver_number'),
                    'lap_number':       msg.get('lap_number'),
                    'qualifying_phase': msg.get('qualifying_phase'),
                })
            conn.commit()

        logger.info(f"  Stored {len(messages)} race control messages")

    def _store_race_results(self, session_key: int, session_id: int):
        """Store final race results from /session_result and grid from /starting_grid."""
        results = openf1_get("session_result", {"session_key": session_key})
        try:
            grid = openf1_get("starting_grid", {"session_key": session_key})
        except Exception:
            grid = []
            logger.warning("  starting_grid not available, grid positions will be empty")

        grid_map = {g.get('driver_number'): g.get('position') for g in grid}

        with self.engine.connect() as conn:
            for r in results:
                driver_num = r.get('driver_number')
                dnf  = bool(r.get('dnf'))
                dns  = bool(r.get('dns'))
                dsq  = bool(r.get('dsq'))
                if dsq:
                    status = 'DSQ'
                elif dns:
                    status = 'DNS'
                elif dnf:
                    status = 'DNF'
                else:
                    status = 'Finished'

                conn.execute(text("""
                    UPDATE drivers SET
                        position      = :pos,
                        grid_position = :grid,
                        dnf           = :dnf,
                        dns           = :dns,
                        dsq           = :dsq,
                        status        = :status,
                        gap_to_leader = :gap,
                        number_of_laps = :laps,
                        race_duration  = :duration
                    WHERE session_id = :session_id AND driver_number = :driver_number
                """), {
                    'pos':           r.get('position'),
                    'grid':          grid_map.get(driver_num),
                    'dnf':           dnf,
                    'dns':           dns,
                    'dsq':           dsq,
                    'status':        status,
                    'gap':           str(r.get('gap_to_leader')) if r.get('gap_to_leader') is not None else None,
                    'laps':          r.get('number_of_laps'),
                    'duration':      r.get('duration'),
                    'session_id':    session_id,
                    'driver_number': driver_num,
                })
            conn.commit()

        logger.info(f"  Stored race results for {len(results)} drivers")

    def _store_qualifying_results(self, session_key: int, session_id: int):
        """Store qualifying positions and best lap from /session_result."""
        results = openf1_get("session_result", {"session_key": session_key})

        with self.engine.connect() as conn:
            for r in results:
                duration = r.get('duration')
                # Qualifying duration comes as an array [Q1, Q2, Q3] — take the best
                if isinstance(duration, list):
                    duration = min(t for t in duration if t is not None) if duration else None

                conn.execute(text("""
                    UPDATE drivers SET
                        position      = :pos,
                        race_duration = :duration
                    WHERE session_id = :session_id AND driver_number = :driver_number
                """), {
                    'pos':           r.get('position'),
                    'duration':      duration,
                    'session_id':    session_id,
                    'driver_number': r.get('driver_number'),
                })
            conn.commit()

        logger.info(f"  Stored qualifying results for {len(results)} drivers")

    def _store_pits(self, session_key: int, session_id: int, driver_map: dict[int, str]):
        pits = openf1_get("pit", {"session_key": session_key})

        with self.engine.connect() as conn:
            for p in pits:
                num = p.get('driver_number')
                conn.execute(text("""
                    INSERT INTO pits (
                        session_id, driver_number, name_acronym,
                        lap_number, stop_duration, lane_duration, date
                    ) VALUES (
                        :session_id, :driver_number, :name_acronym,
                        :lap_number, :stop_duration, :lane_duration, :date
                    )
                """), {
                    'session_id':    session_id,
                    'driver_number': num,
                    'name_acronym':  driver_map.get(num, str(num)),
                    'lap_number':    p.get('lap_number'),
                    'stop_duration': p.get('stop_duration') or p.get('lane_duration'),
                    'lane_duration': p.get('lane_duration'),
                    'date':          p.get('date'),
                })
            conn.commit()

        logger.info(f"  Stored {len(pits)} pit stops")

    def _store_overtakes(self, session_key: int, session_id: int):
        overtakes = openf1_get("overtakes", {"session_key": session_key})

        with self.engine.connect() as conn:
            for o in overtakes:
                conn.execute(text("""
                    INSERT INTO overtakes (
                        session_id, overtaking_driver_number,
                        overtaken_driver_number, position, date
                    ) VALUES (
                        :session_id, :overtaking, :overtaken, :position, :date
                    )
                """), {
                    'session_id': session_id,
                    'overtaking': o.get('overtaking_driver_number'),
                    'overtaken':  o.get('overtaken_driver_number'),
                    'position':   o.get('position'),
                    'date':       o.get('date'),
                })
            conn.commit()

        logger.info(f"  Stored {len(overtakes)} overtakes")


if __name__ == "__main__":
    pipeline = OpenF1Pipeline()

    years         = [2026]
    session_types = ['Qualifying', 'Race']

    for year in years:
        logger.info(f"=== Fetching {year} season ===")
        pipeline.fetch_year(year, session_types)

    print("Fetch complete!")
