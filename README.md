# Quantitative Trading

This repository contains code and resources related to quantitative trading strategies, data analysis, and algorithmic trading. It includes implementations of various trading algorithms, backtesting frameworks, and tools for data visualization and analysis.

## Learning Milestones

- [x] Simple backtest strategy from builtin example with my own datatick from broker
- [ ] Writing an adapter to start paper trading
- [ ] Write my own ICT model strategy
- [ ] Backtest a year of data
- [ ] Start live trading with small cent account

## Project structure

```
QuantNautilus
├── CHANGELOG.md
├── data # Data directory containing datatick and parquet
│   └── dataticks
│       ├── Exness_EURUSDc_2025_09.csv
│       └── Exness_EURUSDc_2025_09.zip
├── docker-compose.yml
├── Dockerfile
├── README.md
├── requirements.txt
└── src
    ├── main.py # Backtest script
    └── strategies # Strategies that use on backtest and live trading
```

## Prerequisites

- Docker or Podman

## Running with Docker or Podman

```bash
docker-compose up --build

# or

podman-compose up --build
```

## Running without Docker and Podman

```bash
git clone <this repo>
cd <this repo>
pip install -r requirements.txt
python3 src/main.py
```
