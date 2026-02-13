import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class DataProcessor:
    """
    Handles data processing and statistical analysis.
    Uses NumPy and Pandas for robust calculations.
    """

    def __init__(self):
        pass

    def calculate_stats(self, data: List[float]) -> Dict[str, float]:
        """
        Calculate basic statistical metrics for a list of numbers.
        """
        if not data:
            return {}

        try:
            arr = np.array(data)
            stats = {
                "mean": float(np.mean(arr)),
                "median": float(np.median(arr)),
                "std_dev": float(np.std(arr)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "variance": float(np.var(arr))
            }
            return stats
        except Exception as e:
            logger.error(f"Error calculating stats: {e}")
            return {"error": str(e)}

    def analyze_timeseries(self, dates: List[Any], values: List[float]) -> Dict[str, Any]:
        """
        Analyze time series data using Pandas.
        """
        if not dates or not values or len(dates) != len(values):
            return {"error": "Invalid input data"}

        try:
            df = pd.DataFrame({"date": dates, "value": values})
            # parse dates if strings
            if isinstance(dates[0], str):
                df["date"] = pd.to_datetime(df["date"])
            
            df.set_index("date", inplace=True)
            
            # Calculate rolling metrics
            df["rolling_mean_7d"] = df["value"].rolling(window=7, min_periods=1).mean()
            
            # Trend (simple linear regression logic via numpy polyfit)
            # x as numeric timestamps
            x = np.arange(len(df))
            y = df["value"].values
            slope, intercept = np.polyfit(x, y, 1)
            
            trend = "stable"
            if slope > 0.05: trend = "increasing"
            elif slope < -0.05: trend = "decreasing"

            return {
                "trend": trend,
                "slope": float(slope),
                "latest_value": float(df["value"].iloc[-1]),
                "rolling_mean_last": float(df["rolling_mean_7d"].iloc[-1])
            }

        except Exception as e:
            logger.error(f"Error analyzing timeseries: {e}")
            return {"error": str(e)}
