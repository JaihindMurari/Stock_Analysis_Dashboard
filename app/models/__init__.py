"""
Database Models — NSE Dashboard
Normalized schema: stocks → prices → indicators → signals
"""
from datetime import datetime
from app import db


class Stock(db.Model):
    """Master list of tracked equities."""
    __tablename__ = 'stocks'

    id          = db.Column(db.Integer, primary_key=True)
    symbol      = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name        = db.Column(db.String(120), nullable=False)
    exchange    = db.Column(db.String(10), nullable=False, default='NSE')  # NSE / BSE
    sector      = db.Column(db.String(60))
    industry    = db.Column(db.String(80))
    market_cap  = db.Column(db.BigInteger)
    is_active   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    prices      = db.relationship('Price',     backref='stock', lazy='dynamic',
                                  cascade='all, delete-orphan')
    indicators  = db.relationship('Indicator', backref='stock', lazy='dynamic',
                                  cascade='all, delete-orphan')
    signals     = db.relationship('Signal',    backref='stock', lazy='dynamic',
                                  cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id, 'symbol': self.symbol, 'name': self.name,
            'exchange': self.exchange, 'sector': self.sector,
            'industry': self.industry, 'market_cap': self.market_cap,
            'is_active': self.is_active,
        }

    def __repr__(self):
        return f'<Stock {self.symbol}>'


class Price(db.Model):
    """OHLCV candle data — one row per stock per interval."""
    __tablename__ = 'prices'
    __table_args__ = (
        db.UniqueConstraint('stock_id', 'datetime', name='uq_price_stock_dt'),
        db.Index('ix_prices_stock_dt', 'stock_id', 'datetime'),
    )

    id        = db.Column(db.Integer, primary_key=True)
    stock_id  = db.Column(db.Integer, db.ForeignKey('stocks.id', ondelete='CASCADE'),
                          nullable=False)
    datetime  = db.Column(db.DateTime, nullable=False)
    open      = db.Column(db.Numeric(12, 4))
    high      = db.Column(db.Numeric(12, 4))
    low       = db.Column(db.Numeric(12, 4))
    close     = db.Column(db.Numeric(12, 4))
    volume    = db.Column(db.BigInteger)
    adj_close = db.Column(db.Numeric(12, 4))

    def to_dict(self):
        return {
            'datetime': self.datetime.isoformat(),
            'open': float(self.open or 0), 'high': float(self.high or 0),
            'low': float(self.low or 0),   'close': float(self.close or 0),
            'volume': self.volume,          'adj_close': float(self.adj_close or 0),
        }


class Indicator(db.Model):
    """Computed technical indicators for each candle."""
    __tablename__ = 'indicators'
    __table_args__ = (
        db.UniqueConstraint('stock_id', 'datetime', name='uq_ind_stock_dt'),
        db.Index('ix_indicators_stock_dt', 'stock_id', 'datetime'),
    )

    id        = db.Column(db.Integer, primary_key=True)
    stock_id  = db.Column(db.Integer, db.ForeignKey('stocks.id', ondelete='CASCADE'),
                          nullable=False)
    datetime  = db.Column(db.DateTime, nullable=False)
    sma_20    = db.Column(db.Numeric(12, 4))
    sma_50    = db.Column(db.Numeric(12, 4))
    sma_200   = db.Column(db.Numeric(12, 4))
    ema_12    = db.Column(db.Numeric(12, 4))
    ema_26    = db.Column(db.Numeric(12, 4))
    rsi       = db.Column(db.Numeric(8, 4))
    macd      = db.Column(db.Numeric(12, 6))
    macd_signal = db.Column(db.Numeric(12, 6))
    macd_hist   = db.Column(db.Numeric(12, 6))
    bb_upper    = db.Column(db.Numeric(12, 4))
    bb_middle   = db.Column(db.Numeric(12, 4))
    bb_lower    = db.Column(db.Numeric(12, 4))

    def to_dict(self):
        def _f(v):
            return float(v) if v is not None else None
        return {
            'datetime': self.datetime.isoformat(),
            'sma_20': _f(self.sma_20), 'sma_50': _f(self.sma_50),
            'sma_200': _f(self.sma_200), 'ema_12': _f(self.ema_12),
            'ema_26': _f(self.ema_26), 'rsi': _f(self.rsi),
            'macd': _f(self.macd), 'macd_signal': _f(self.macd_signal),
            'macd_hist': _f(self.macd_hist),
            'bb_upper': _f(self.bb_upper), 'bb_middle': _f(self.bb_middle),
            'bb_lower': _f(self.bb_lower),
        }


class Signal(db.Model):
    """Trading signals derived from indicator logic."""
    __tablename__ = 'signals'
    __table_args__ = (
        db.UniqueConstraint('stock_id', 'datetime', name='uq_sig_stock_dt'),
    )

    SIGNAL_TYPES = ('BUY', 'SELL', 'HOLD')

    id          = db.Column(db.Integer, primary_key=True)
    stock_id    = db.Column(db.Integer, db.ForeignKey('stocks.id', ondelete='CASCADE'),
                            nullable=False)
    datetime    = db.Column(db.DateTime, nullable=False)
    signal_type = db.Column(db.Enum(*SIGNAL_TYPES), nullable=False)
    confidence  = db.Column(db.Numeric(5, 2))    # 0–100
    reason      = db.Column(db.Text)

    def to_dict(self):
        return {
            'datetime': self.datetime.isoformat(),
            'signal': self.signal_type,
            'confidence': float(self.confidence or 0),
            'reason': self.reason,
        }
