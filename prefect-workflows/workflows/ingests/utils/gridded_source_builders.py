from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional, Iterable

from teehr.fetching.utils import (
    REMOTE_RETRY_CONFIG,
    build_remote_nwm_filelist,
    end_on_z_hour,
    start_on_z_hour,
    validate_nwm_version_against_files,
)


class GriddedSource(ABC):
    source_bucket: str
    # Source-specific obstore kwargs; deployment obstore_kwargs override them
    store_kwargs: dict = {}

    @abstractmethod
    def build_file_list(self, start_dt: datetime, end_dt: datetime) -> list[str]: ...


class UASwan4km(GriddedSource):
    source_bucket = "https://climate.arizona.edu"

    def __init__(self, status: list[str] = None):
        # status controls which data variant to fetch: "stable", "provisional", or "early".
        self.status = status or ["stable", "provisional", "early"]

    def build_file_list(self, start_dt: datetime, end_dt: datetime) -> list[str]:
        """Build UA SWANN 4km daily SWE/depth file URLs for the given date range and status(es)."""
        file_list = []
        current = start_dt.date()
        end = end_dt.date()
        while current <= end:
            # Water year starts October 1; directories are organized by water year
            wy = current.year + 1 if current.month >= 10 else current.year
            for s in self.status:
                file_list.append(
                    f"https://climate.arizona.edu/data/UA_SWE/DailyData_4km/"
                    f"WY{wy}/UA_SWE_Depth_4km_v1_{current:%Y%m%d}_{s}.nc"
                )
            current += timedelta(days=1)
        return file_list


class NWMForcing(GriddedSource):
    source_bucket = "gs://national-water-model"
    store_kwargs = {"retry_config": REMOTE_RETRY_CONFIG}

    def __init__(
        self,
        configuration: str,
        output_type: str,
        analysis_config_dict: dict,
        nwm_version: str,
        t_minus_hours: Optional[Iterable[int]] = [0],
        ignore_missing_file: bool = True,
        prioritize_analysis_value_time: bool = False,
        drop_overlapping_assimilation_values: bool = False,
    ):
        self.configuration = configuration
        self.output_type = output_type
        self.analysis_config_dict = analysis_config_dict
        self.nwm_version = nwm_version
        self.t_minus_hours = t_minus_hours
        self.ignore_missing_file = ignore_missing_file
        self.prioritize_analysis_value_time = prioritize_analysis_value_time
        self.drop_overlapping_assimilation_values = drop_overlapping_assimilation_values

    def build_file_list(self, start_dt: datetime, end_dt: datetime) -> list[str]:
        file_list = build_remote_nwm_filelist(
            configuration=self.configuration,
            output_type=self.output_type,
            start_dt=start_dt,
            end_dt=end_dt,
            analysis_config_dict=self.analysis_config_dict,
            t_minus_hours=self.t_minus_hours,
            ignore_missing_file=self.ignore_missing_file,
            prioritize_analysis_value_time=self.prioritize_analysis_value_time,
            drop_overlapping_assimilation_values=self.drop_overlapping_assimilation_values,
        )
        # teehr lists whole days; clip the first and last days by reference time (z-hour), as teehr's fetching does
        if file_list:
            file_list = start_on_z_hour(start_z_hour=start_dt.hour, gcs_component_paths=sorted(file_list))
            file_list = end_on_z_hour(end_z_hour=end_dt.hour, gcs_component_paths=file_list)
        # Raise if the files report a different NWM version than requested
        validate_nwm_version_against_files(file_list, self.nwm_version)
        # Replace the gcs prefix with gs
        return [f.replace("gcs://", "gs://") for f in file_list]
