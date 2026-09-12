"""Create deterministic, overlapping filing and article retrieval chunks."""

from document_text import build_research_chunks
from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql import types as T

CHUNK_SCHEMA = T.ArrayType(
    T.StructType(
        [
            T.StructField("chunk_id", T.StringType()),
            T.StructField("parent_id", T.StringType()),
            T.StructField("chunk_index", T.IntegerType()),
            T.StructField("section_name", T.StringType()),
            T.StructField("chunk_text", T.StringType()),
            T.StructField("chunk_to_retrieve", T.StringType()),
            T.StructField("chunk_to_embed", T.StringType()),
            T.StructField("chunk_token_count", T.IntegerType()),
            T.StructField("parent_text", T.StringType()),
            T.StructField("parent_token_count", T.IntegerType()),
            T.StructField("chunk_content_hash", T.StringType()),
            T.StructField("source_content_hash", T.StringType()),
        ]
    )
)
chunk_document = F.udf(
    lambda source_type, source_id, text, title, ticker, source_date, document_kind: build_research_chunks(
        source_type,
        source_id,
        text,
        title=title,
        ticker=ticker,
        source_date=source_date,
        document_kind=document_kind,
    ),
    CHUNK_SCHEMA,
)


@dp.materialized_view(
    name="silver_research_chunks",
    comment="Stable filing and article retrieval chunks with exact source identity and URL provenance.",
    cluster_by=["source_type", "ticker", "source_date"],
    table_properties={
        "delta.enableRowTracking": "true",
        "delta.enableChangeDataFeed": "true",
    },
)
@dp.expect_all_or_fail(
    {
        "chunk_id_valid": "chunk_id RLIKE '^[a-f0-9]{64}$'",
        "source_identity_present": "source_id IS NOT NULL",
        "source_url_present": "source_url RLIKE '^https?://'",
        "chunk_text_present": "length(chunk_text) > 0",
        "embedding_text_present": "length(chunk_to_embed) >= length(chunk_to_retrieve)",
        "child_token_bound": "chunk_token_count BETWEEN 1 AND 650",
        "parent_token_bound": "parent_token_count BETWEEN chunk_token_count AND 1600",
    }
)
def silver_research_chunks():
    filing_documents = spark.read.table("bronze_sec_filing_documents")  # noqa: F821
    filings = spark.read.table("silver_sec_filings")  # noqa: F821 - injected by Databricks SDP
    companies = spark.read.table("silver_sec_companies").select(  # noqa: F821
        "cik", "ticker", "company_name"
    )
    filing_sources = filing_documents.alias("documents").join(
        filings.alias("filings"), ["cik", "accession_number"]
    ).join(companies.alias("companies"), ["cik", "ticker"]).select(
        F.lit("filing").alias("source_type"),
        F.col("accession_number").alias("source_id"),
        F.array("ticker").alias("tickers"),
        "ticker",
        F.col("company_name").alias("title"),
        F.col("filing_date").alias("source_date"),
        F.col("filings.source_url").alias("source_url"),
        F.col("filings.fetched_at").alias("fetched_at"),
        "document_text",
        "selected_sections",
        "base_form",
    )
    article_tickers = spark.read.table("silver_article_tickers").groupBy("article_id").agg(  # noqa: F821
        F.sort_array(F.collect_set("ticker")).alias("tickers")
    )
    article_sources = (
        spark.read.table("silver_research_articles")  # noqa: F821 - injected by Databricks SDP
        .join(article_tickers, "article_id")
        .select(
            F.lit("article").alias("source_type"),
            F.col("article_id").alias("source_id"),
            "tickers",
            F.element_at("tickers", 1).alias("ticker"),
            "title",
            F.to_date("published_at").alias("source_date"),
            "article_url",
            "ingested_at",
            F.concat_ws("\n\n", "title", "description").alias("document_text"),
            F.array().cast("array<string>").alias("selected_sections"),
            F.lit("news article").alias("base_form"),
        )
        .withColumnRenamed("article_url", "source_url")
        .withColumnRenamed("ingested_at", "fetched_at")
    )
    sources = filing_sources.unionByName(article_sources)
    return (
        sources.withColumn(
            "chunk",
            F.explode(
                chunk_document(
                    "source_type",
                    "source_id",
                    "document_text",
                    "title",
                    "ticker",
                    "source_date",
                    "base_form",
                )
            ),
        )
        .select(
            F.col("chunk.chunk_id").alias("chunk_id"),
            F.col("chunk.parent_id").alias("parent_id"),
            "source_type",
            "source_id",
            "tickers",
            "ticker",
            "title",
            "source_date",
            "source_url",
            "fetched_at",
            "selected_sections",
            F.col("chunk.chunk_index").alias("chunk_index"),
            F.col("chunk.section_name").alias("section_name"),
            F.col("chunk.chunk_text").alias("chunk_text"),
            F.col("chunk.chunk_to_retrieve").alias("chunk_to_retrieve"),
            F.col("chunk.chunk_to_embed").alias("chunk_to_embed"),
            F.col("chunk.chunk_token_count").alias("chunk_token_count"),
            F.col("chunk.parent_text").alias("parent_text"),
            F.col("chunk.parent_token_count").alias("parent_token_count"),
            F.col("chunk.chunk_content_hash").alias("chunk_content_hash"),
            F.col("chunk.source_content_hash").alias("source_content_hash"),
        )
    )
