AI Trading Bot
==============

FastAPI-based trading bot with this workflow:

Market Data -> Analysis -> AI Decision -> Risk Check -> Trade -> Save Data -> Dashboard APIs

Components
----------

- Trading engine: Python service (Render)
- Exchange: OKX API
- Database: Supabase (REST API, optional but supported)
- Dashboard: Vercel frontend consuming this API

Run Locally
-----------

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start API:

```bash
uvicorn app.main:app --reload
```

3. Start trading loop manually:

```bash
python scripts/run_cycle.py
```

Frontend (Next.js on Vercel)
----------------------------

Frontend lives in `trading-bot-frontend/`.

1. Install and run locally:

```bash
cd trading-bot-frontend
npm install
npm run dev
```

2. Set environment variable in Vercel:

- `NEXT_PUBLIC_API_BASE_URL=https://<your-render-backend>.onrender.com`

3. In Vercel project settings:

- Root Directory: `trading-bot-frontend`
- Build Command: `npm run build`
- Output Directory: `.next`

Frontend routes:

- `/login` and `/register` (session-based auth UI)
- `/dashboard` (live bot metrics/trades/signals)
- `/settings` (edit and save `RISK_CONFIG` + `STRATEGY_CONFIG`)

Environment Variables
---------------------

Only minimal bootstrap config is in environment:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `LOG_LEVEL` (optional)
- `SETTINGS_CACHE_TTL_SECONDS` (optional, default `20`)
- `CORS_ORIGINS` (optional, comma-separated, default `*`)

All trading/exchange/AI/risk values are read from DB table `bot_settings`.
Active symbols are read from `bot_symbols` using `market_type` (`spot`/`swap`) and `is_active`.
OKX credentials are mode-aware: set both `OKX_TESTNET_*` and `OKX_LIVE_*`; bot picks one based on `OKX_MODE`.

Supabase setup:

- Run `supabase_schema.sql` in Supabase SQL editor before using DB-backed endpoints.

Seed `bot_settings` example:

```sql
insert into public.bot_settings (key, value) values
('OKX_TESTNET_API_KEY', 'testnet_key'),
('OKX_TESTNET_SECRET', 'testnet_secret'),
('OKX_TESTNET_PASSPHRASE', 'testnet_passphrase'),
('OKX_LIVE_API_KEY', 'live_key'),
('OKX_LIVE_SECRET', 'live_secret'),
('OKX_LIVE_PASSPHRASE', 'live_passphrase'),
('OKX_MODE', 'testnet'),
('TRADING_CANDLE_LIMIT', '200'),
('LOOP_INTERVAL_SECONDS', '60'),
('DRY_RUN', 'true'),
('GEMINI_API_KEY', ''),
('GEMINI_MODEL', 'gemini-1.5-flash'),
('RISK_CONFIG', '{"autoTrading":true,"maxCapitalAllocation":10000,"riskPerTradeType":"PERCENT","maxRiskPerTrade":1,"maxDrawdown":20,"maxDailyLoss":500,"maxOpenPositions":5,"maxExposurePerPair":25,"maxLeverage":5,"marginType":"CROSS","trailingStop":false,"riskLevelProfile":"MODERATE"}'),
('STRATEGY_CONFIG', '{"activeStrategy":"TREND","aiEnabled":false,"minConfidence":70,"timeframe":"1m","orderType":"MARKET","allowedSpotAssets":["BTC","ETH"],"allowedSwapAssets":["BTC","ETH"],"blockedAssets":[],"minVolume":0,"globalTakeProfit":0,"globalStopLoss":0,"indicators":{"rsi":true,"macd":true,"ema":true,"volume":true},"telegram":{"enabled":false,"botToken":"","chatId":""}}'),
('AUTO_START_CYCLE', 'false')
on conflict (key) do update set value = excluded.value, updated_at = now();
```

Seed `bot_symbols` example:

```sql
insert into public.bot_symbols (symbol, market_type, is_active) values
('BTC-USDT', 'spot', true),
('ETH-USDT', 'spot', true),
('BTC-USDT-SWAP', 'swap', true),
('ETH-USDT-SWAP', 'swap', false);
```

API Endpoints
-------------

- `GET /health`
- `GET /status`
- `GET /config`
- `POST /cycle/run`
- `GET /signals`
- `GET /trades`
- `GET /positions`
- `GET /pnl`
