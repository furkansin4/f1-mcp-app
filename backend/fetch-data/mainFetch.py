import fastf1
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import logging
import json
from typing import Dict
import os
import time

logging.basicConfig(filename= '2021f1.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class F1DataPipeline:
    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize the F1 data pipeline
        
        Args:
            db_config: Dictionary containing database connection parameters
                      {'host': 'localhost', 'database': 'f1_data', 'user': 'username', 'password': 'password', 'port': '5432'}
        """
        self.db_config = db_config
        self.engine = self._create_engine()

    def _create_engine(self):
        """Create SQLAlchemy engine for PostgreSQL connection"""
        connection_string = f"postgresql://{self.db_config['user']}:@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
        return create_engine(connection_string)
    
    def fetch_and_store_session(self, year: int, event: str, session: str):
        """
        Fetch all data for a specific F1 session and store in PostgreSQL
        
        Args:
            year: Season year (e.g., 2023)
            event: Event name (e.g., 'Bahrain', 'Monaco')
            session: Session type ('FP1', 'FP2', 'FP3', 'Qualifying', 'Sprint', 'Race')
        """
        logger.info(f"Fetching data for {year} {event} {session}")
        
        try:
            # Get session data
            f1_session = fastf1.get_session(year, event, session)
            f1_session.load(laps=True, telemetry=True, weather=True, messages=True)
            
            # Store session metadata
            session_id = self._store_session_metadata(f1_session, year, event, session)

            # Store driver/results
            self._store_drivers(f1_session, session_id)

            # Store laps data
            self._store_laps(f1_session, session_id)

            # Store telemetry
            self._store_telemetry(f1_session, session_id)

            self._store_weather(f1_session, session_id)

            self._store_session_status(f1_session, session_id)

            self._store_track_status(f1_session, session_id)

            self._store_race_control_messages(f1_session, session_id)

            if session == 'R':
                self._store_circuit_info(f1_session, session_id)
            
            logger.info(f"Successfully stored all data for {year} {event} {session}")
            return session_id
            
        except Exception as e:
            logger.error(f"Error processing session {year} {event} {session}: {e}")
            raise

    def convert_datetime_to_string(self, obj):
        """Convert datetime and timedelta objects to serializable formats"""
        if isinstance(obj, dict):
            return {key: self.convert_datetime_to_string(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self.convert_datetime_to_string(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, timedelta):
            return obj.total_seconds()  # Convert to seconds as float
        else:
            return obj
        
    def convert_timedelta_for_db(self, obj):
        """Convert timedelta objects to None or string format for database compatibility"""
        if isinstance(obj, timedelta):
            # PostgreSQL interval format or None
            return None
        return obj
    
    def process_dataframe_for_db(self, df):
        """Process DataFrame to convert timedelta columns for database storage"""
        df_copy = df.copy()
        for col in df_copy.columns:
            if df_copy[col].dtype == 'timedelta64[ns]':
                df_copy[col] = df_copy[col].apply(lambda x: str(x) if pd.notna(x) else None)
        return df_copy
    
    def _store_session_metadata(self, session, year: int, event: str, session_name: str) -> int:
        """Store session metadata and return session_id"""

        session_info_dict = None
        if hasattr(session, 'session_info'):
            session_info_dict = self.convert_datetime_to_string(dict(session.session_info))
        
        # Handle timedelta conversion for session_start_time
        session_start_time = None
        if hasattr(session, 'session_start_time') and session.session_start_time is not None:
            session_start_time = self.convert_timedelta_for_db(session.session_start_time)
        
        session_data = {
            'season': year,
            'event_name': event,
            'session_name': session_name,
            'date': session.date if hasattr(session, 'date') else None,
            'api_path': session.api_path if hasattr(session, 'api_path') else None,
            'session_info': json.dumps(session_info_dict) if hasattr(session, 'session_info') else None,
            'f1_api_support': session.f1_api_support if hasattr(session, 'f1_api_support') else None,
            'total_laps': session.total_laps if hasattr(session, 'total_laps') else None,
            'session_start_time': session_start_time,
            't0_date': session.t0_date if hasattr(session, 't0_date') else None
        }
        
        df = pd.DataFrame([session_data])
        df = self.process_dataframe_for_db(df)
        df.to_sql('sessions', self.engine, if_exists='append', index=False, method='multi')
        
        # Get the session_id
        with self.engine.connect() as conn:
            result = conn.execute(text(
                "SELECT id FROM sessions WHERE season = :year AND event_name = :event AND session_name = :session ORDER BY id DESC LIMIT 1"
            ), {"year": year, "event": event, "session": session_name})
            session_id = result.fetchone()[0]
        
        logger.info(f"Stored session metadata with ID: {session_id}")
        return session_id
    
    def _store_drivers(self, session, session_id: int):
        """Store driver/results data"""
        
        if not hasattr(session, 'results') or session.results.empty:
            logger.warning("No driver results data available")
            return
        
        results_df = session.results.copy()
        results_df['session_id'] = session_id
        
        # Handle DNF property if available
        if hasattr(session.results.iloc[0], 'dnf'):
            results_df['dnf'] = [driver.dnf for _, driver in session.results.iterrows()]
        
        # Map FastF1 columns to database columns
        column_mapping = {
            'DriverNumber': 'driver_number',
            'BroadcastName': 'broadcast_name',
            'FullName': 'full_name',
            'Abbreviation': 'driver_id',
            'DriverId': 'driver_name',
            'TeamName': 'team_name',
            'TeamColor': 'team_color',
            'TeamId': 'team_id',
            'FirstName': 'first_name',
            'LastName': 'last_name',
            'HeadshotUrl': 'headshot_url',
            'CountryCode': 'country_code',
            'Position': 'position',
            'ClassifiedPosition': 'classified_position',
            'GridPosition': 'grid_position',
            'Q1': 'q1_time',
            'Q2': 'q2_time',
            'Q3': 'q3_time',
            'Time': 'race_time',
            'Status': 'status',
            'Points': 'points'
        }
        
        results_df = results_df.rename(columns=column_mapping)
        
        # Select only columns that exist in the dataframe and are in our table
        existing_columns = [col for col in column_mapping.values() if col in results_df.columns]
        existing_columns.append('session_id')
        if 'dnf' in results_df.columns:
            existing_columns.append('dnf')
        
        results_df = results_df[existing_columns]
        
        results_df = self.process_dataframe_for_db(results_df)
        results_df.to_sql('drivers', self.engine, if_exists='append', index=False, method='multi')
        logger.info(f"Stored {len(results_df)} driver records")

    def _store_laps(self, session, session_id: int):
        """Store laps data"""
        if not hasattr(session, 'laps') or session.laps.empty:
            logger.warning("No laps data available")
            return
        
        laps_df = session.laps.copy()
        laps_df['session_id'] = session_id

        # Map FastF1 columns to database columns
        column_mapping = {
            'Driver': 'driver_id',
            'LapNumber': 'lap_number',
            'LapTime': 'lap_time',
            'LapStartTime': 'lap_start_time',
            'LapStartDate': 'lap_start_date',
            'Stint': 'stint',
            'PitOutTime': 'pit_out_time',
            'PitInTime': 'pit_in_time',
            'Sector1Time': 'sector1_time',
            'Sector2Time': 'sector2_time',
            'Sector3Time': 'sector3_time',
            'Sector1SessionTime': 'sector1_session_time',
            'Sector2SessionTime': 'sector2_session_time',
            'Sector3SessionTime': 'sector3_session_time',
            'SpeedI1': 'speed_i1',
            'SpeedI2': 'speed_i2',
            'SpeedFL': 'speed_fl',
            'SpeedST': 'speed_st',
            'IsPersonalBest': 'is_personal_best',
            'Compound': 'compound',
            'TyreLife': 'tyre_life',
            'FreshTyre': 'fresh_tyre',
            'Team': 'team',
            'TrackStatus': 'track_status',
            'Position': 'position',
            'Deleted': 'deleted',
            'DeletedReason': 'deleted_reason',
            'FastF1Generated': 'fastf1_generated',
            'IsAccurate': 'is_accurate',
            'Time': 'session_time'
        }
        
        laps_df = laps_df.rename(columns=column_mapping)

        # Select only existing columns
        existing_columns = [col for col in column_mapping.values() if col in laps_df.columns]
        existing_columns.append('session_id')
        laps_df = laps_df[existing_columns]

        # Handle batch insertion for large datasets
        batch_size = 1000
        for i in range(0, len(laps_df), batch_size):
            batch = laps_df.iloc[i:i+batch_size]
            batch = self.process_dataframe_for_db(batch)
            batch.to_sql('laps', self.engine, if_exists='append', index=False, method='multi')
            logger.info(f"Stored laps batch {i//batch_size + 1}/{(len(laps_df)-1)//batch_size + 1}")
        
        logger.info(f"Stored {len(laps_df)} lap records")

    def _store_telemetry(self, session, session_id: int):
        """Store telemetry data for all drivers"""
        logger.info("Starting telemetry data processing")
        
        # Check if laps data is available
        if session.laps.empty:
            logger.warning("No laps data available for telemetry")
            return
        
        total_records = 0
        
        # Get unique drivers from the session
        drivers = session.laps['Driver'].unique()
        
        for driver in drivers:
            try:
                logger.info(f"Processing telemetry for driver {driver}")
                
                # Get all laps for that driver
                driver_laps = session.laps[session.laps['Driver'] == driver]
                
                if driver_laps.empty:
                    logger.warning(f"No laps found for driver {driver}")
                    continue
                
                # Get driver number (convert driver abbreviation/name to number if needed)
                try:
                    # Try to get driver number from results
                    driver_info = session.results[session.results['Abbreviation'] == driver]
                    if not driver_info.empty:
                        driver_number = driver_info.iloc[0]['DriverNumber']
                    else:
                        # Fallback: use the driver identifier as is
                        driver_number = driver
                except:
                    driver_number = driver
                
                # Collect telemetry data for all laps of this driver
                all_telemetry_data = []
                
                for idx, lap in driver_laps.iterrows():
                    try:
                        # Get telemetry for this specific lap
                        lap_telemetry = lap.get_telemetry()
                        
                        if lap_telemetry.empty:
                            continue
                        
                        # Add lap number to telemetry data
                        lap_telemetry = lap_telemetry.copy()
                        lap_telemetry['lap_number'] = lap['LapNumber']
                        
                        all_telemetry_data.append(lap_telemetry)
                        
                    except Exception as e:
                        logger.warning(f"Error getting telemetry for driver {driver}, lap {lap['LapNumber']}: {e}")
                        continue
                
                if not all_telemetry_data:
                    logger.warning(f"No telemetry data collected for driver {driver}")
                    continue
                
                # Concatenate all telemetry data for this driver
                telemetry_data = pd.concat(all_telemetry_data, ignore_index=True)
                
                # Prepare dataframe for database
                telemetry_df = telemetry_data.copy()
                telemetry_df['session_id'] = session_id
                telemetry_df['driver_number'] = str(driver_number)
                telemetry_df['driver_id'] = str(driver)  # Add driver_id field
                
                # Map columns
                column_mapping = {
                    'Speed': 'speed',
                    'RPM': 'rpm',
                    'nGear': 'n_gear',
                    'Throttle': 'throttle',
                    'Brake': 'brake',
                    'DRS': 'drs',
                    'X': 'x_position',
                    'Y': 'y_position',
                    'Z': 'z_position',
                    'Status': 'status',
                    'Source': 'source',
                    'Time': 'time_elapsed',
                    'SessionTime': 'session_time',
                    'Date': 'date_time',
                    'Distance': 'distance',
                    'RelativeDistance': 'relative_distance',
                    'DriverAhead': 'driver_ahead',
                    'DistanceToDriverAhead': 'distance_to_driver_ahead'
                }
                
                telemetry_df = telemetry_df.rename(columns=column_mapping)
                
                # Select existing columns
                required_columns = ['session_id', 'driver_id', 'driver_number', 'lap_number']
                optional_columns = [col for col in column_mapping.values() if col in telemetry_df.columns]
                existing_columns = required_columns + optional_columns
                
                # Filter to only include columns that exist in the dataframe
                final_columns = [col for col in existing_columns if col in telemetry_df.columns]
                telemetry_df = telemetry_df[final_columns]
                
                # Store in batches to handle large datasets
                batch_size = 5000
                for i in range(0, len(telemetry_df), batch_size):
                    batch = telemetry_df.iloc[i:i+batch_size]
                    batch = self.process_dataframe_for_db(batch)
                    batch.to_sql('telemetry', self.engine, if_exists='append', index=False, method='multi')
                    
                total_records += len(telemetry_df)
                logger.info(f"Stored {len(telemetry_df)} telemetry records for driver {driver}")
                
            except Exception as e:
                logger.error(f"Error processing telemetry for driver {driver}: {e}")
                continue
        
        logger.info(f"Stored {total_records} total telemetry records")

    def _store_weather(self, session, session_id: int):
        """Store weather data"""
        logger.info("Starting weather data processing")

        weather_df = session.laps.get_weather_data().copy()

        # Check if weather data is available
        if weather_df.empty:
            logger.warning("No weather data available")
            return
        
        weather_df['session_id'] = session_id

        column_mapping = {
            'Time': 'session_time',
            'AirTemp': 'air_temp',
            'Humidity': 'humidity',
            'Pressure': 'pressure',
            'Rainfall': 'rainfall',
            'TrackTemp': 'track_temp',
            'WindDirection': 'wind_direction',
            'WindSpeed': 'wind_speed' 
        }

        weather_df = weather_df.rename(columns=column_mapping)

        # Process and store directly (no batching)
        weather_df = self.process_dataframe_for_db(weather_df)
        weather_df.to_sql('weather', self.engine, if_exists='append', index=False, method='multi')
        
        logger.info(f"Stored {len(weather_df)} weather records")

    def _store_session_status(self, session, session_id: int):
        """Store session status data"""
        logger.info("Starting session status data processing")

        status_df = session.session_status.copy()

        # Check if weather data is available
        if status_df.empty:
            logger.warning("No session status data available")
            return
        
        status_df['session_id'] = session_id

        column_mapping = {
            'Time': 'session_time',
            'Status': 'status'
        }

        status_df = status_df.rename(columns=column_mapping)

        # Process and store directly (no batching)
        status_df = self.process_dataframe_for_db(status_df)
        status_df.to_sql('session_status', self.engine, if_exists='append', index=False, method='multi')
        
        logger.info(f"Stored session status")

    def _store_track_status(self, session, session_id: int):
        """Store track status data"""
        logger.info("Starting session status data processing")

        track_df = session.track_status.copy()

        # Check if track data is available
        if track_df.empty:
            logger.warning("No track status data available")
            return
        
        track_df['session_id'] = session_id

        column_mapping = {
            'Time': 'session_time',
            'Status': 'status',
            'Message': 'message'
        }

        track_df = track_df.rename(columns=column_mapping)

        # Process and store directly (no batching)
        track_df = self.process_dataframe_for_db(track_df)
        track_df.to_sql('track_status', self.engine, if_exists='append', index=False, method='multi')
        
        logger.info(f"Stored track status")

    def _store_race_control_messages(self, session, session_id: int):
        """Store race control messages data"""
        logger.info("Starting race control messages data processing")

        race_control_df = session.race_control_messages.copy()

        # Check if track data is available
        if race_control_df.empty:
            logger.warning("No race control messages data available")
            return
        
        race_control_df['session_id'] = session_id

        column_mapping = {
            'Time': 'utc',
            'Category': 'category',
            'Message': 'message',
            'Status': 'status',
            'Flag': 'flag',
            'Scope': 'scope',
            'Sector': 'sector',
            'RacingNumber': 'racing_number',
            'Lap': 'lap'
        }

        race_control_df = race_control_df.rename(columns=column_mapping)

        race_control_df = self.process_dataframe_for_db(race_control_df)
        race_control_df.to_sql('race_control', self.engine, if_exists='append', index=False, method='multi')
        
        logger.info(f"Stored race control messages")

    def _store_circuit_info(self, session, session_id: int):
        """Store circuit info data"""
        logger.info("Starting circuit info data processing")
        
        circuit_info = session.get_circuit_info()

        all_markers = []
        
        # Define common column mapping for all circuit info types
        column_mapping = {
            'X': 'x_position',
            'Y': 'y_position',
            'Number': 'number',
            'Letter': 'letter',
            'Angle': 'angle',
            'Distance': 'distance',
            'Rotation': 'rotation'
        }
        
        # Corners
        if hasattr(circuit_info, 'corners') and not circuit_info.corners.empty:
            corners_data = circuit_info.corners.copy()
            corners_data['info_type'] = 'corners'  # Changed from marker_type to info_type to match schema
            corners_data['session_id'] = session_id
            
            # Apply column mapping
            corners_data = corners_data.rename(columns=column_mapping)
            all_markers.append(corners_data)
        
        # Marshal lights
        if hasattr(circuit_info, 'marshal_lights') and not circuit_info.marshal_lights.empty:
            lights_data = circuit_info.marshal_lights.copy()
            lights_data['info_type'] = 'marshal_lights'
            lights_data['session_id'] = session_id
            
            # Apply column mapping
            lights_data = lights_data.rename(columns=column_mapping)
            all_markers.append(lights_data)
        
        # Marshal sectors
        if hasattr(circuit_info, 'marshal_sectors') and not circuit_info.marshal_sectors.empty:
            sectors_data = circuit_info.marshal_sectors.copy()
            sectors_data['info_type'] = 'marshal_sectors'
            sectors_data['session_id'] = session_id
            
            # Apply column mapping
            sectors_data = sectors_data.rename(columns=column_mapping)
            all_markers.append(sectors_data)
        
        # Combine all data
        if all_markers:
            combined_df = pd.concat(all_markers, ignore_index=True)
            
            # Select only columns that exist in both the dataframe and our table schema
            expected_columns = ['session_id', 'info_type', 'x_position', 'y_position', 
                            'number', 'letter', 'angle', 'distance', 'rotation']
            existing_columns = [col for col in expected_columns if col in combined_df.columns]
            combined_df = combined_df[existing_columns]
            
            # Process for database compatibility
            combined_df = self.process_dataframe_for_db(combined_df)
            combined_df.to_sql('circuit_info', self.engine, if_exists='append', index=False, method='multi')
            logger.info(f"Stored {len(combined_df)} circuit info records")
        else:
            logger.warning("No circuit info data available")

if __name__ == "__main__":
    # Database configuration
    db_config = {
        'user': 'furkansina',
        'host': 'localhost',
        'port': '5432',
        'database': 'f1',
    }

    # Enable FastF1 cache for better performance
    cache_dir = '/Users/furkansina/Library/Caches/fastf1'
    os.makedirs(cache_dir, exist_ok=True)
    fastf1.Cache.enable_cache(cache_dir)

    try:
        # Initialize pipeline
        pipeline = F1DataPipeline(db_config)

        years = range(2019,2024)
        session_types = ['Q', 'R']


        start_year = 2021
        start_event_name = "Hungarian Grand Prix"
        start_session_type = "R"

        start_processing = False  # Flag to control where to begin

        for year in range(2019, 2024):
            schedule = fastf1.get_event_schedule(year)

            for index, event in schedule.iterrows():
                event_name = event["EventName"]

                if not start_processing:
                    if year == start_year and event_name == start_event_name:
                        start_processing = True
                        session_start_index = session_types.index(start_session_type)
                        session_range = session_types[session_start_index:]
                    else:
                        continue
                else:
                    session_range = session_types

                for session_type in session_range:
                    try:
                        pipeline.fetch_and_store_session(year, event_name, session_type)
                        logger.info(f"✓ {year} {event_name} {session_type}")
                    except Exception as e:
                        logger.info(f"✗ {year} {event_name} {session_type}: {e}")
                        continue

                # Clear cache after each event
                cache_path, cache_size = fastf1.Cache.get_cache_info()
                if cache_path and cache_size > 0:
                    logger.info(f"  Clearing cache after {event_name} ({cache_size/1024/1024:.1f} MB)...")
                    fastf1.Cache.clear_cache(f'/Users/furkansina/Library/Caches/fastf1/{year}/', deep=True)

        # for year in years:

        #     schedule = fastf1.get_event_schedule(year)
            
        #     for index, event in schedule.iterrows():
        #         event_name = event["EventName"]
        #         for session_type in session_types:
        #             try:
        #                 pipeline.fetch_and_store_session(year, event_name, session_type)
        #                 logger.info(f"✓ {year} {event_name} {session_type}")
        #             except Exception as e:
        #                 logger.info(f"✗ {year} {event_name} {session_type}: {e}")
        #                 continue
                    
        #         # Clear cache after each event (after all its sessions)
        #         cache_path, cache_size = fastf1.Cache.get_cache_info()
        #         if cache_path and cache_size > 0:
        #             logger.info(f"  Clearing cache after {event_name} ({cache_size/1024/1024:.1f} MB)...")
        #             fastf1.Cache.clear_cache(f'/Users/furkansina/Library/Caches/fastf1/{year}/', deep=True)
    
    finally:
        print("\nFinal cleanup...")
        fastf1.Cache.clear_cache('/Users/furkansina/Library/Caches/fastf1/2025/', deep=True)
        print("Scraping complete!")


