# Scripts

Start and stop the FinAlly Docker container.

## macOS / Linux

Make the shell scripts executable after cloning (one-time setup):

```bash
chmod +x scripts/*.sh
```

Then:

```bash
# Start (builds image automatically on first run)
./scripts/start_mac.sh

# Force rebuild
./scripts/start_mac.sh --build

# Stop
./scripts/stop_mac.sh
```

## Windows (PowerShell)

```powershell
# Start (builds image automatically on first run)
.\scripts\start_windows.ps1

# Force rebuild
.\scripts\start_windows.ps1 -Build

# Stop
.\scripts\stop_windows.ps1
```

## Notes

- Data persists in a Docker named volume (`finally-data`). Stopping the container does not delete data.
- Requires a `.env` file in the project root. Copy `.env.example` and fill in `OPENCODE_API_KEY`.
