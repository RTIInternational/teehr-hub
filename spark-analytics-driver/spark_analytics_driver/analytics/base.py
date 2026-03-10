"""
Base class for analytics implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

import teehr


class BaseAnalytics(ABC):
    """Base class for analytics implementations."""

    @abstractmethod
    def run(
        self,
        ev: teehr.Evaluation,
        run_id: str,
        parameters: Dict[str, Any],
    ) -> str:
        """Run the analytics.

        Parameters
        ----------
        ev : teehr.Evaluation
            The teehr evaluation object with Spark session.
        run_id : str
            Unique identifier for this run.
        parameters : dict
            Analytics parameters from the API request.

        Returns
        -------
        str
            Name of the result table created in teehr_results schema.
        """
        pass
