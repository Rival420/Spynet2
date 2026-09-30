# Spynet

Spynet watches your home network from a Raspberry Pi (or any Linux box) and
answers one question at a glance: **is everything on my network something I
recognize, and is it up?**

It sweeps the network with ARP every few seconds, keeps a device inventory
keyed by MAC address (so DHCP address changes do not create duplicates),
records when devices join and leave, scans for open ports in the background,
and pushes everything live to a dashboard. New, unrecognized devices are the
loudest thing on screen until you name them.

## What it does

- **Presence.** ARP sweep on a schedule you choose (default every 30 s). A
  device is online while it answers and goes offline after a grace period,
  so phones that nap do not flap.
- **Device inventory.** MAC, current and previous IP, vendor (looked up once
  and cached), discovered hostname (reverse DNS, mDNS, NetBIOS), your own
  name, type and notes. Randomized "private" MAC addresses are recognized as
  such.
- **New-device detection.** Anything never seen before is flagged
  *Unrecognized* until you mark it. "Recognize all" makes the first run
  painless.
- **Activity log.** New device, came online, went offline, changed IP,
  opened or closed ports. Filterable per device.
- **Port scans.** A quick scan of ~60 common ports runs automatically for
  each device (interval configurable), with diffs logged. Range and full
  scans on demand, plus banner grabbing and one-click "Open" for web UIs.
- **Notifications.** A JSON webhook fires on the events you choose. Works
  with Home Assistant webhooks, ntfy, n8n, Discord relays and similar.
- **Runs unattended.** Settings persist in SQLite, the scanner resumes on
  boot, and the systemd unit restarts it if it ever dies.
- **One process.** Flask serves the API, Socket.IO pushes updates and the
  built React dashboard is served from the same port. No CORS setup, no
  hard-coded IPs.

## Running on a Raspberry Pi (recommended)

Tested on Raspberry Pi OS Bookworm (64-bit) on a Pi 3B+, 4 and 5. The Pi
must be on the network you want to watch, ideally by Ethernet.

### Option A: build on your computer, deploy over SSH

This avoids building the frontend on the Pi. You need Node 18+ and `rsync`
locally, and SSH access to the Pi.

```bash
git clone https://github.com/Rival420/Spynet2.git
cd Spynet2
make deploy PI=pi@raspberrypi.local
```

`make deploy` builds the dashboard, copies the project to `~/spynet` on the
Pi and runs the installer there with sudo. Re-run it any time to upgrade.

### Option B: everything on the Pi

```bash
sudo apt install -y git nodejs npm
git clone https://github.com/Rival420/Spynet2.git
cd Spynet2
sudo ./deploy/install.sh
```

If the Pi's Node is older than 18 the installer says so; use option A or
install a newer Node (for example from NodeSource) and re-run.

### What the installer does

- Installs the code to `/opt/spynet` and creates a Python virtualenv there.
- Stores the database in `/var/lib/spynet/spynet.db`, owned by a dedicated
  `spynet` system user.
- Installs and enables the `spynet` systemd service. It runs as that user,
  not root: the unit grants only `CAP_NET_RAW` and `CAP_NET_ADMIN`, which is
  what ARP needs, and locks the rest of the filesystem read-only.
- Starts the service. The dashboard is at `http://<pi-ip>:5000`.

### Day-to-day on the Pi

```bash
sudo systemctl status spynet       # is it running?
journalctl -u spynet -f            # live logs
sudo systemctl restart spynet      # after changing the unit or env
```

On first open, the dashboard asks which network to watch (it detects the
Pi's own subnet), then starts. The scanner resumes automatically after a
reboot or a crash as long as you left it running. Pressing **Stop** in the
dashboard also disables the resume-on-boot behaviour; **Start** re-enables it.

To change the port or database location, edit the `Environment=` lines in
`/etc/systemd/system/spynet.service`, then
`sudo systemctl daemon-reload && sudo systemctl restart spynet`.

## Running anywhere else

Requirements: Python 3.9+, Node 18+ (only to build the dashboard), and raw
socket permission (root/sudo, or the capabilities above).

```bash
make venv          # python3 -m venv .venv && pip install -r requirements.txt
make build         # builds spynet/dist
make run           # sudo .venv/bin/python server.py  -> http://localhost:5000
```

Environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `SPYNET_HOST` | `0.0.0.0` | Bind address |
| `SPYNET_PORT` | `5000` | Port for API and dashboard |
| `SPYNET_DB` | `./spynet.db` | SQLite database path |
| `SPYNET_NETWORK` | *(auto)* | Network to watch in CIDR, used when nothing is configured yet |
| `SPYNET_FRONTEND_DIR` | `./spynet/dist` | Where the built dashboard lives |
| `SPYNET_PORT_WORKERS` | `128` | Concurrent connections during a port scan |

### Developing the dashboard

```bash
make dev-api                 # backend on :5000 (needs sudo)
cd spynet && npm run dev     # Vite dev server on :3000 with hot reload, proxies /api and /socket.io
```

If the backend runs on another machine, put its URL in `spynet/.env` as
`VITE_API_ENDPOINT` (see `.env.example`).

## Notifications

Set a webhook URL in Settings. Spynet sends `POST` with JSON:

```json
{
  "source": "spynet",
  "event": { "kind": "new_device", "message": "New device 192.168.1.99 (Private address)", "mac": "…", "ip": "…", "ts": "…", "details": {} },
  "device": { "mac": "…", "ip": "…", "name": "…", "vendor": "…", "ports": [80, 443], "known": false, … }
}
```

Home Assistant example: create an automation with a *Webhook* trigger with
id `spynet`, then use
`http://homeassistant.local:8123/api/webhook/spynet` as the URL. The event is
available as `trigger.json.event` in the automation.

## API

All endpoints return JSON. The dashboard uses nothing else, so anything it
can do you can script.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/state` | Devices, recent events, scanner status and settings in one call |
| GET | `/api/devices` | All devices |
| GET | `/api/devices/export.csv` | Inventory as CSV |
| GET | `/api/devices/<mac>` | One device with its event history |
| PATCH | `/api/devices/<mac>` | Set `name`, `notes`, `device_type`, `known` |
| DELETE | `/api/devices/<mac>` | Forget a device (it returns as new if seen again) |
| POST | `/api/devices/acknowledge_all` | Mark every device as recognized |
| POST | `/api/devices/<mac>/portscan` | `{"mode": "quick"\|"range"\|"full", "start", "end"}` |
| POST | `/api/devices/<mac>/banner` | `{"port": 22}` |
| POST | `/api/devices/<mac>/refresh` | Re-run vendor and hostname lookup |
| GET | `/api/events?limit=&mac=&kind=` | Event log |
| DELETE | `/api/events` | Clear the log |
| GET/POST | `/api/scanner`, `/api/scanner/{start,pause,resume,stop,sweep}` | Scanner control |
| GET | `/api/network/detect` | The local subnet as seen from the server |
| GET/PUT | `/api/settings` | Read or update settings |
| POST | `/api/settings/test_webhook` | Send a test notification |

Socket.IO events pushed to clients: `devices` (full list), `device` (one
changed or `{deleted: true}`), `event`, `scanner`, `settings`.

## Security notes

Spynet has no authentication. Keep it on your LAN or put it behind a reverse
proxy with auth if you expose it. It only ever talks to devices on the
configured network plus `api.macvendors.com` for vendor names (rate limited
to one lookup per second, cached forever) and your webhook URL.

## Upgrading from the 2025 version

The old database (one row per IP) is imported automatically the first time
the new version starts: hostnames you set become device names, and those
devices are marked as recognized. The installer copies an existing
`spynet.db` from the checkout into `/var/lib/spynet` if there is none there.

## License

MIT, see [LICENSE](LICENSE).
