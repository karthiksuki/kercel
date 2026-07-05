# Contributing

Thank you for your interest in contributing to Kercel!

## Reporting Issues

Before creating a new issue, please check if a similar issue already exists.

When reporting a bug, include:

- A clear description of the problem
- Steps to reproduce it
- Expected behavior
- Screenshots or logs (if applicable)
- Your environment (OS, Python version, Node.js version)

## Development Setup

Clone the repository.

```bash
git clone https://github.com/karthiksuki/kercel.git
cd kercel
```

### Backend

```bash
cd infra

python -m venv .venv
```

**macOS / Linux**

```bash
source .venv/bin/activate
```

**Windows (PowerShell)**

```powershell
.venv\Scripts\Activate
```

Install dependencies.

```bash
pip install -r requirements.txt
```

### Frontend

```bash
cd ../web

npm install
npm run dev
```

## Pull Requests

Before opening a pull request:

- Keep changes focused on a single feature or fix.
- Follow the existing code style.
- Test your changes locally.
- Update documentation if necessary.

## Commit Messages

Please use clear commit messages.

Examples:

```
feat: add deployment retry support

fix: handle failed GitHub clone

docs: update README

refactor: simplify deployment worker
```

## Code Style

### Python

- Follow the code style.
- Use meaningful variable names
- Keep functions focused and small

### TypeScript / React

- Prefer functional components
- Keep components reusable
- Use consistent formatting

## Questions

If you're unsure about a change, feel free to open a discussion or draft pull request before implementing it.

Thanks for contributing...