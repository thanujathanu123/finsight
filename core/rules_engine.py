"""Financial risk detection engine using pandas and machine learning.

This module handles CSV/Excel parsing and risk scoring using both rules-based
and machine learning approaches for detecting suspicious transactions.
"""
import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any, Optional
from datetime import datetime
from .risk_ml import RiskScorer


class InvalidFileError(Exception):
    """Raised when the input file is invalid or missing required columns."""
    pass


def validate_columns(df: pd.DataFrame) -> None:
    """Check if DataFrame has required columns."""
    required = {'date', 'description', 'amount'}
    missing = required - set(df.columns)
    if missing:
        raise InvalidFileError(
            f"Missing required columns: {', '.join(missing)}. "
            f"Found columns: {', '.join(df.columns)}"
        )


def parse_ledger_file(file_path: str) -> pd.DataFrame:
    """Parse CSV/Excel file into a DataFrame with basic validation.
    
    Args:
        file_path: Path to CSV or Excel file
        
    Returns:
        DataFrame with standardized columns
        
    Raises:
        InvalidFileError: If file format or content is invalid
    """
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_path)
        else:
            raise InvalidFileError("Unsupported file format. Use CSV or Excel.")
        
        # Standardize column names (case-insensitive)
        df.columns = df.columns.str.lower().str.strip()
        
        # Validate required columns
        validate_columns(df)
        
        # Convert date strings to datetime
        df['date'] = pd.to_datetime(df['date'])
        
        # Ensure amount is numeric
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        
        # Drop rows with null amounts
        df = df.dropna(subset=['amount'])
        
        return df
        
    except pd.errors.EmptyDataError:
        raise InvalidFileError("File is empty")
    except pd.errors.ParserError as e:
        raise InvalidFileError(f"Could not parse file: {str(e)}")


def compute_risk_metrics(df: pd.DataFrame) -> Dict[str, float]:
    """Compute various risk metrics for the entire ledger.
    
    Returns:
        Dict with overall metrics like total transactions, volume, etc.
    """
    metrics = {
        'total_transactions': len(df),
        'total_volume': df['amount'].abs().sum(),
        'unique_descriptions': df['description'].nunique(),
        'date_range_days': (df['date'].max() - df['date'].min()).days,
    }
    return metrics


def compute_risk_scores(
    df: pd.DataFrame,
    risk_profile: Optional[Dict] = None,
    historical_data: Optional[pd.DataFrame] = None
) -> Tuple[pd.DataFrame, float]:
    """Analyze transactions and compute risk scores using ML and rules.
    
    Args:
        df: DataFrame of transactions to analyze
        risk_profile: Optional risk profile configuration
        historical_data: Optional historical data for ML training
        
    Returns:
        Tuple of (DataFrame with risk scores and factors, overall risk score)
    """
    df = df.copy()
    
    # Initialize risk scorer
    scorer = RiskScorer(risk_profile)
    
    # Train on historical data if provided
    if historical_data is not None and not historical_data.empty:
        scorer.fit(historical_data)
    
    # Analyze the ledger
    analysis = scorer.analyze_ledger(df)
    
    return analysis['scored_transactions'], float(analysis['overall_risk'])
