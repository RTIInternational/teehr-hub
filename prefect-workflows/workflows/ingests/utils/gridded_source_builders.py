from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Iterable

from teehr.fetching.utils import build_remote_nwm_filelist


class GriddedSource(ABC):
    source_bucket: str

    @abstractmethod
    def build_file_list(self, start_dt: datetime, end_dt: datetime) -> list[str]: ...


class NWMForcing(GriddedSource):
    source_bucket = "gs://national-water-model"

    def __init__(
        self,
        configuration: str,
        output_type: str,
        analysis_config_dict: dict,
        t_minus_hours: Optional[Iterable[int]] = None,
        ignore_missing_file: bool = True,
        prioritize_analysis_value_time: bool = True,
        drop_overlapping_assimilation_values: bool = True,
    ):
        self.configuration = configuration
        self.output_type = output_type
        self.analysis_config_dict = analysis_config_dict
        self.t_minus_hours = t_minus_hours
        self.ignore_missing_file = ignore_missing_file
        self.prioritize_analysis_value_time = prioritize_analysis_value_time
        self.drop_overlapping_assimilation_values = drop_overlapping_assimilation_values

    def build_file_list(self, start_dt: datetime, end_dt: datetime) -> list[str]:
        return build_remote_nwm_filelist(
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
