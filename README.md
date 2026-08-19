# Quantitative Trading

Unofficial MetaTrader5 adapter for NautilusTrader.

# What this is?

nautilus_mt5 is a adapter for NautilusTrader that containt data and execution client for live trading and fetch data for backtest session.

## Prerequisites

- Docker

# Quick Start

## Installation

git clone https://codeberg.org/hitagi/nautilus_mt5
cd nautilus_mt5
pip install -e .

## Initialization

1. Create a .env file in your project root. You can see example in examples/.env.example
2. Run the MetaTrader5 platform with docker
3. Open localhost:60832/vnc.html for access to MetaTrader5 platform throught noVNC
4. Find your server name in MetaTrader5 platform
5. Enable AutoTrading
6. Test the connection with test/test_pymt5linux.py
7. Now the MetaTrader5 platform is ready to use for live or backtest session

## Backtest

You can see example in examples/backtest for more information

## Live

You can see example in examples/live for more information
