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

- Docker

## Running with container

- Docker

```bash
docker-compose up --build
```

## Running without container

1. Clone this repository

```bash
git clone <this repository>
```

2. Navigate to the project directory

```bash
cd <this repo>
```

3. Install the required Python packages

```bash
pip install -r requirements.txt
```

4. Run the backtest

```bash
python3 src/main.py
```

## Testing strategy

### Running tests

- Full test suite

```bash
docker-compose -f docker-compose.test.yml up test
```

- Quick unit tests only

```bash
docker-compose run test pytest tests/unit/ -m fast
```

- With coverage report

```bash
docker-compose run test pytest --cov=src --cov-report=html
```
