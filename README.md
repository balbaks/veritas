# VERITAS — Trust Inversion Protocol Core

Layer 0 of the Veritas Trust Ecosystem.

A protocol for verifiable trust. Submit claims. Gather proofs. Compute trust scores. All backed by cryptographic verification, not platform authority.

## Running (Docker)

docker build -t veritas-node .
docker run -d -p 8000:8000 veritas-node
curl http://localhost:8000/

## Running (Local)

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn api.server:app --reload --port 8000

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | / | Protocol status |
| POST | /claim | Submit a claim |
| POST | /proof | Submit a proof |
| GET | /trust?claim_id= | Get trust verdict |

Interactive docs: http://localhost:8000/docs

## Tech Stack

- Python 3.12
- FastAPI
- SQLite (aiosqlite)
- Docker

## License

MIT
