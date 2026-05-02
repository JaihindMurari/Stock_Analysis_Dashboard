-- ═══════════════════════════════════════════════════════════════
-- MarketPulse India — MySQL Schema
-- Run this ONCE to bootstrap the database, or use Flask-Migrate
-- ═══════════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS nse_dashboard
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE nse_dashboard;

-- ── stocks ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stocks (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  symbol      VARCHAR(20)  NOT NULL UNIQUE COMMENT 'yfinance symbol e.g. TCS.NS',
  name        VARCHAR(120) NOT NULL,
  exchange    VARCHAR(10)  NOT NULL DEFAULT 'NSE',
  sector      VARCHAR(60),
  industry    VARCHAR(80),
  market_cap  BIGINT UNSIGNED,
  is_active   TINYINT(1)   NOT NULL DEFAULT 1,
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX ix_stocks_symbol (symbol),
  INDEX ix_stocks_exchange (exchange)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── prices ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prices (
  id        INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  stock_id  INT UNSIGNED NOT NULL,
  datetime  DATETIME     NOT NULL,
  open      DECIMAL(12,4),
  high      DECIMAL(12,4),
  low       DECIMAL(12,4),
  close     DECIMAL(12,4),
  volume    BIGINT UNSIGNED,
  adj_close DECIMAL(12,4),
  UNIQUE KEY uq_price_stock_dt (stock_id, datetime),
  INDEX ix_prices_stock_dt (stock_id, datetime),
  CONSTRAINT fk_prices_stock FOREIGN KEY (stock_id)
    REFERENCES stocks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── indicators ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS indicators (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  stock_id    INT UNSIGNED NOT NULL,
  datetime    DATETIME     NOT NULL,
  sma_20      DECIMAL(12,4),
  sma_50      DECIMAL(12,4),
  sma_200     DECIMAL(12,4),
  ema_12      DECIMAL(12,4),
  ema_26      DECIMAL(12,4),
  rsi         DECIMAL(8,4),
  macd        DECIMAL(12,6),
  macd_signal DECIMAL(12,6),
  macd_hist   DECIMAL(12,6),
  bb_upper    DECIMAL(12,4),
  bb_middle   DECIMAL(12,4),
  bb_lower    DECIMAL(12,4),
  UNIQUE KEY uq_ind_stock_dt (stock_id, datetime),
  INDEX ix_indicators_stock_dt (stock_id, datetime),
  CONSTRAINT fk_indicators_stock FOREIGN KEY (stock_id)
    REFERENCES stocks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── signals ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS signals (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  stock_id    INT UNSIGNED NOT NULL,
  datetime    DATETIME     NOT NULL,
  signal_type ENUM('BUY','SELL','HOLD') NOT NULL,
  confidence  DECIMAL(5,2),
  reason      TEXT,
  UNIQUE KEY uq_sig_stock_dt (stock_id, datetime),
  INDEX ix_signals_stock_id (stock_id),
  INDEX ix_signals_type (signal_type),
  CONSTRAINT fk_signals_stock FOREIGN KEY (stock_id)
    REFERENCES stocks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Helpful views ──────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_latest_prices AS
  SELECT p.*, s.symbol, s.name, s.exchange, s.sector
  FROM prices p
  JOIN stocks s ON s.id = p.stock_id
  WHERE (p.stock_id, p.datetime) IN (
    SELECT stock_id, MAX(datetime) FROM prices GROUP BY stock_id
  );

CREATE OR REPLACE VIEW vw_latest_signals AS
  SELECT sg.*, s.symbol, s.name, s.sector
  FROM signals sg
  JOIN stocks s ON s.id = sg.stock_id
  WHERE (sg.stock_id, sg.datetime) IN (
    SELECT stock_id, MAX(datetime) FROM signals GROUP BY stock_id
  );
