create table if not exists public.signals (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  symbol text not null,
  signal text not null,
  final_signal text not null,
  trend text,
  price double precision,
  rsi double precision,
  atr double precision,
  strategy_reasons jsonb,
  ai_confidence double precision,
  ai_reason text
);

create table if not exists public.trades (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  symbol text not null,
  side text not null,
  entry_price double precision,
  size double precision,
  stop_loss double precision,
  take_profit double precision,
  risk_amount double precision,
  order_id text,
  status text,
  realized_pnl double precision default 0
);

create table if not exists public.positions (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  symbol text not null,
  side text,
  size double precision,
  entry_price double precision,
  unrealized_pnl double precision,
  stop_loss double precision,
  take_profit double precision,
  status text,
  source text
);

create table if not exists public.pnl (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  symbol text,
  value double precision,
  details jsonb
);

create table if not exists public.cycles (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  timestamp timestamptz,
  symbol text,
  strategy_signal text,
  final_signal text,
  trade_status text,
  trade_reason text,
  risk_plan jsonb
);

create table if not exists public.bot_settings (
  key text primary key,
  value text,
  updated_at timestamptz not null default now()
);

create table if not exists public.bot_symbols (
  id bigint generated always as identity primary key,
  symbol text not null,
  market_type text not null check (market_type in ('spot', 'swap')),
  is_active boolean not null default true,
  updated_at timestamptz not null default now()
);
