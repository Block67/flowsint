# Flowtrace

[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](./LICENSE)
[![Ethical Software](https://img.shields.io/badge/ethical-use-blue.svg)](./ETHICS.md)

Flowtrace is an open-source, graph-based tool for **transaction analysis and fund tracing** across bank accounts, mobile money and crypto wallets. Accounts are nodes, transactions are edges, and the graph shows where money comes from and where it goes.

Flowtrace is a fork of [Flowsint](https://github.com/reconurge/flowsint) by Reconurge, refocused from general OSINT on financial flows. See [NOTICE](./NOTICE).

**Ethics:** Please read [ETHICS.md](./ETHICS.md) for responsible use guidelines.

## Features

**Data in**
- **Statement import** from CSV or Excel (bank, mobile money, card): ledger files (one row per transfer, with sender and receiver) or account statements (debit/credit columns). Columns are suggested automatically from French or English headers, with a preview before import.
- **Ethereum and EVM chains** (Etherscan v2: Ethereum, BSC, Polygon, Arbitrum, Optimism, Base, Avalanche): native transactions and ERC-20 token transfers.
- **Bitcoin** (mempool.space): transfers attributed per input and output, without change outputs.
- **TRON** (TronGrid): TRC-20 transfers, USDT by default.
- **OFAC sanctions check** for crypto addresses.

**Analysis**
- **Pattern detection**: fan-in, fan-out, pass-through (money mule) accounts, structuring below a reporting threshold, circular flows.
- **Fund tracing** upstream or downstream from any account, respecting the order of transactions in time.
- **Account summaries**: received, sent, net balance, counterparties, active period.

**Interface**
- Edge thickness follows the amount, and edges are labelled with it.
- Filters by date range and minimum amount.
- A Transactions view with a sortable ledger and per-account totals.

## Data model

| Type | Identified by |
|---|---|
| `BankAccount` | account number, labelled with the bank |
| `MobileMoneyAccount` | phone number (E.164) + provider |
| `CreditCard` | card number |
| `CryptoWallet` | address (+ chain) |
| `Merchant` | name as it appears on statements |

A transaction is a `TRANSACTION` edge between two of these accounts. It carries the amount, currency, date, channel, reference and, when known, the USD value.

## Get started

### 1. Install prerequisites

- Docker
- Make (Linux / macOS)

### 2. Run

```bash
make dev
```

`make dev` creates the `.env` files from `.env.example` if they are missing.

On Windows (cmd or PowerShell, no Make):

```bat
copy .env.example .env
copy .env.example flowsint-api\.env
copy .env.example flowsint-core\.env
copy .env.example flowsint-app\.env
docker compose -f docker-compose.dev.yml up -d --build
```

Then open [http://localhost:5173/register](http://localhost:5173/register) and create an account. There is no default account. Everything is stored on your machine.

> ⚠️ Do not use `make prod` or `docker-compose.prod.yml` yet: they pull the upstream Flowsint images from `ghcr.io/reconurge`, which do not include any Flowtrace changes. Production images for Flowtrace still need to be built and published.

### API keys

Some enrichers need a key, stored encrypted in the in-app vault:

| Key | Used for |
|---|---|
| `ETHERSCAN_API_KEY` | Ethereum / EVM transactions, tokens and NFTs (free at etherscan.io) |
| `TRONGRID_API_KEY` | Optional, raises TronGrid rate limits |

Bitcoin (mempool.space) and the OFAC lists need no key.

### Before exposing to a network

Change the default secrets in `.env`:

- `AUTH_SECRET` signs authentication tokens. Generate one: `openssl rand -hex 32`
- `MASTER_VAULT_KEY_V1` encrypts stored API keys. Generate one: `python3 -c "import os, base64; print('base64:' + base64.b64encode(os.urandom(32)).decode())"`
- `NEO4J_PASSWORD` is the Neo4j database password.

Also add your server hostname or IP to the Host-header allowlist in `flowsint-app/nginx.conf` (`map $http_host $is_flowsint_host`).

The internal module and package names (`flowsint-*`) are unchanged from upstream.

## Project structure

The project is organized into autonomous modules:

### Core modules

- **flowsint-core**: Core utilities, orchestrator, vault, celery tasks, and base classes
- **flowsint-types**: Pydantic models and type definitions
- **flowsint-enrichers**: Enricher modules, scanning logic, and tools
- **flowsint-api**: FastAPI server, API routes, and schemas only
- **flowsint-app**: Frontend application

### Module dependencies

```
flowsint-app (frontend)
    ↓
flowsint-api (API server)
    ↓
flowsint-core (orchestrator, tasks, vault)
    ↓
flowsint-enrichers (enrichers & tools)
    ↓
flowsint-types (types)
```

## Development setup

### Prerequisites

- Docker

### Run

**Linux / macOS** (requires **Make**):

```bash
make dev
```

**Windows** (cmd or PowerShell, no Make — create the `.env` files first, see [Get started](#windows)):

```bat
docker compose -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.dev.yml logs -f
```

### Development

The app is accessible at [http://localhost:5173](http://localhost:5173).

## Module details

### flowsint-core

Core utilities and base classes used by all other modules:

- Database connections (PostgreSQL, Neo4j)
- Authentication and authorization
- Logging and event handling
- Configuration management
- Base classes for enrichers and tools
- Utility functions

### flowsint-types

Pydantic models for all data types:

- Domain, IP, ASN, CIDR
- Individual, Organization, Email, Phone
- Website, Social profiles, Credentials
- Crypto wallets, Transactions, NFTs
- And many more...

### flowsint-enrichers

Enricher modules that process data:

- Domain enrichers (subdomains, WHOIS, resolution)
- IP enrichers (geolocation, ASN lookup)
- Social media enrichers (Maigret, Sherlock)
- Email enrichers (breaches, Gravatar)
- Crypto enrichers (transactions, NFTs)
- And many more...

### flowsint-api

FastAPI server providing:

- REST API endpoints
- Authentication and user management
- Graph database integration
- Real-time event streaming

### flowsint-app

Frontend application.

- Modern and UI friendly interface
- Built for performance (no lag even on thousands of nodes)

## Development workflow

1. **Adding new types**: Add to `flowsint-types` module
2. **Adding new enrichers**: Add to `flowsint-enrichers` module
3. **Adding new API endpoints**: Add to `flowsint-api` module
4. **Adding new utilities**: Add to `flowsint-core` module

## Testing

Each module has its own (incomplete) test suite:

```bash
# Test core module
cd flowsint-core
uv run pytest

# Test types module
cd ../flowsint-types
uv run pytest

# Test enrichers module
cd ../flowsint-enrichers
uv run pytest

# Test API module
cd ../flowsint-api
uv run pytest
```

## Contributing

1. Follow the modular structure
2. Use [uv](https://docs.astral.sh/uv/) for dependency management
3. Write tests for new functionality
4. Update documentation as needed
5. See [CONTRIBUTING.md](./CONTRIBUTING.md) for the checks to run before committing



---

## ⚖️ Legal & Ethical Use

**Ethics:** Please read [ETHICS.md](./ETHICS.md) for responsible use guidelines.

Flowtrace is designed **strictly for lawful, ethical investigation and research purposes**, such as fraud investigations, anti-money-laundering reviews, compliance and incident response, and journalism.

**Flowtrace must not be used for:**
- Unauthorized access to financial data or accounts
- Surveillance, harassment or targeting of individuals
- Violating banking secrecy, data protection or privacy laws

Statements and transaction data are often personal data: only import what you are authorized to process.

## Credits

Flowtrace is based on [Flowsint](https://github.com/reconurge/flowsint), © 2025-2026 Reconurge, licensed under the [Apache License 2.0](./LICENSE). Consider [supporting the upstream project](https://ko-fi.com/P5P01W3GPJ).
