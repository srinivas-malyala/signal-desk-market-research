CREATE TABLE IF NOT EXISTS {{table:news_article_tickers}} (
  article_id TEXT NOT NULL REFERENCES {{table:news_articles}}(id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  sentiment TEXT,
  sentiment_reasoning TEXT,
  linked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(article_id, ticker)
);
CREATE INDEX IF NOT EXISTS {{index:idx_news_article_tickers_ticker}}
  ON {{table:news_article_tickers}}(ticker);
ALTER TABLE {{table:news_article_tickers}} REPLICA IDENTITY FULL;
