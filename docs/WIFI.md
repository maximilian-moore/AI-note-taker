# Connecting the device to Wi-Fi

The firmware uses a **captive-portal setup** (WiFiManager) — you never hard-code
credentials, and you can change networks later without reflashing.

## First-time setup
1. Power on the freshly flashed device. The e-paper shows a **Setup** screen.
2. On your **phone or laptop**, open Wi-Fi settings and join the network:
   - **Name:** `PocketScribe-Setup`
   - **Password:** `pocket1234`  *(change `SETUP_AP_PASSWORD` in `config.h` before building if you like)*
3. A **configuration page opens automatically** (if not, browse to `http://192.168.4.1`).
4. Tap **Configure Wi-Fi**, pick your home network, and enter its password.
5. Also fill in the two custom fields:
   - **Backend URL** — where your server runs, e.g. `http://192.168.1.20:8080`
   - **Pairing token** — must equal `DEVICE_PAIRING_TOKEN` in the backend `.env`
6. **Save.** The device reboots, joins your Wi-Fi, and shows the Home screen.

These settings are stored in flash (NVS) and reused on every boot.

## What "connected" looks like
The **Home** screen shows `Wi-Fi OK` and a battery %. If it can't reach the
backend, sync will say **No Wi-Fi** or fail — re-check the Backend URL and that
your server is running and reachable on the LAN.

## Changing networks or backend later
- **Moved house / new router / server IP changed:** the device re-opens
  `PocketScribe-Setup` automatically if it can't join the saved network. To force
  it, **hold Button A while powering the device on** — it boots straight into the
  setup portal so you can change the Wi-Fi, Backend URL, or pairing token.
- **Tip for a stable server address:** give your home server a **static/reserved
  IP** in your router, or a hostname, so the Backend URL doesn't drift.

## Reaching the dashboard away from home (optional, Phase 2)
Wi-Fi setup above puts the device and dashboard on your LAN. To open the
dashboard from anywhere, expose the backend on your own domain over HTTPS — a
**Cloudflare Tunnel** is the no-port-forwarding option (see `docker-compose.yml`
for the commented `cloudflared` service and `docs/` for setup).
