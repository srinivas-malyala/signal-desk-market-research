"""Shared schemas and configuration for the market-data SDP datasets."""

from pyspark.sql import types as T

MARKET_BAR_SCHEMA = T.StructType(
    [
        T.StructField("T", T.StringType()),
        T.StructField("v", T.DoubleType()),
        T.StructField("vw", T.DoubleType()),
        T.StructField("o", T.DoubleType()),
        T.StructField("c", T.DoubleType()),
        T.StructField("h", T.DoubleType()),
        T.StructField("l", T.DoubleType()),
        T.StructField("t", T.LongType()),
        T.StructField("n", T.LongType()),
        T.StructField("otc", T.BooleanType()),
    ]
)

MARKET_RESPONSE_SCHEMA = T.StructType(
    [
        T.StructField("adjusted", T.BooleanType()),
        T.StructField("count", T.LongType()),
        T.StructField("queryCount", T.LongType()),
        T.StructField("request_id", T.StringType()),
        T.StructField("results", T.ArrayType(MARKET_BAR_SCHEMA)),
        T.StructField("resultsCount", T.LongType()),
        T.StructField("status", T.StringType()),
        T.StructField("_rescued_data", T.StringType()),
    ]
)

MARKET_MANIFEST_SCHEMA = T.StructType(
    [
        T.StructField("version", T.IntegerType()),
        T.StructField("source", T.StringType()),
        T.StructField("dataset", T.StringType()),
        T.StructField("trading_date", T.StringType()),
        T.StructField("endpoint", T.StringType()),
        T.StructField("adjusted", T.BooleanType()),
        T.StructField("include_otc", T.BooleanType()),
        T.StructField("request_id", T.StringType()),
        T.StructField("correlation_id", T.StringType()),
        T.StructField("status_code", T.IntegerType()),
        T.StructField("row_count", T.LongType()),
        T.StructField("byte_count", T.LongType()),
        T.StructField("checksum_sha256", T.StringType()),
        T.StructField("elapsed_ms", T.LongType()),
        T.StructField("landed_at", T.StringType()),
        T.StructField("response_path", T.StringType()),
        T.StructField("_rescued_data", T.StringType()),
    ]
)

MARKET_QUALITY_RULES = (
    ("schema_rescued", "rescued_data IS NOT NULL"),
    ("missing_ticker", "ticker_raw IS NULL"),
    ("invalid_ticker", "NOT ticker_raw RLIKE '^[A-Z][A-Z0-9.-]{0,9}$'"),
    ("missing_trading_date", "trading_date IS NULL"),
    ("missing_event_timestamp", "event_timestamp IS NULL"),
    ("missing_price", "open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL"),
    ("negative_price", "open < 0 OR high < 0 OR low < 0 OR close < 0"),
    ("invalid_high", "high < greatest(open, close, low)"),
    ("invalid_low", "low > least(open, close, high)"),
    ("invalid_volume", "volume IS NULL OR volume < 0"),
    ("invalid_vwap", "vwap < 0"),
    ("invalid_transactions", "transactions < 0"),
)


def raw_market_path(spark) -> str:
    """Return the configured root of the immutable market landing area."""
    return f"{spark.conf.get('signal_desk.raw_volume_path').rstrip('/')}/market_daily"
