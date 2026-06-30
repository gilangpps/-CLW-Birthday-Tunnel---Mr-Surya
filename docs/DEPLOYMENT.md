# Event Deployment Checklist

## Before Event Day

1. Install Python 3.10 or newer on the TouchDesigner/server machine.
2. Run `run_event_server.bat` once to create the virtual environment and install dependencies.
3. Open `http://localhost:8080/` and submit a test message with a photo.
4. Confirm the photo appears in `data/images/`.
5. Confirm metadata appears in `data/submissions.json`.
6. Confirm `http://localhost:8080/api/submissions` returns JSON.
7. Build the TouchDesigner template and connect it to `touchdesigner/td_bridge.py`.

## Network Setup

Use a dedicated local router for stability.

1. Connect the TouchDesigner PC by Ethernet if possible.
2. Connect the tablet and visitor Wi-Fi to the same router.
3. Find the PC IP address:

```powershell
ipconfig
```

Use the IPv4 address on the venue router, for example `192.168.1.20`.

Visitor URL:

```text
http://192.168.1.20:8080/
```

Tablet QR page:

```text
http://192.168.1.20:8080/qr
```

## Windows Firewall

When Python first runs the server, Windows may ask for network permission.

Allow access on the private/local network.

If blocked, create an inbound rule for TCP port `8080`.

## TouchDesigner Runtime

Recommended values for a clean videotron tunnel:

```python
MAX_ACTIVE_ITEMS = 18
ITEM_LIFETIME_SECONDS = 32.0
SHUFFLE_INTERVAL_SECONDS = 12.0
POLL_INTERVAL_SECONDS = 1.5
```

Adjust live only after checking readability from audience distance.

## Operator Run Order

1. Start router.
2. Start server with `run_event_server.bat`.
3. Open tablet page `/qr`.
4. Open admin page `/admin`.
5. Start TouchDesigner project.
6. Submit one test entry.
7. Confirm TouchDesigner receives and displays it.
8. Reset all test data from admin if needed.
9. Begin event.

## Failure Handling

If visitor phones cannot open the form:

- Confirm they are on the correct Wi-Fi.
- Confirm the URL uses the PC IP, not `localhost`.
- Confirm Python server window is still running.
- Confirm Windows Firewall allows port `8080`.

If TouchDesigner stops updating:

- Check `http://localhost:8080/api/health`.
- Press manual refresh in your TD operator UI if you wire `manualRefresh()`.
- Restart only the TD bridge runtime if visuals are stuck; stored submissions remain safe.

If submissions spike:

- Do not raise active count too high.
- Let queue absorb the spike.
- Shorten item lifetime slightly if the scene feels stale.
- Keep image TOP/movie reloads pooled and recycled.

## Post Event

Back up:

```text
data/submissions.json
data/images/
data/logs/
```

These contain the full event archive.
