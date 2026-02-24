# Frontend

Next.js dashboard for the Ball Knowledge match recommender.

## Prerequisites

- Node.js 20+
- Backend API running (default: `http://127.0.0.1:8000`)

## Environment

Create `.env.local` from `.env.example`:

```bash
cp .env.example .env.local
```

Set:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## Run

```bash
npm install
npm run dev
```

## Quality Checks

```bash
npm run lint
npm run build
```
