# Midea M-Control (Cloud + Local) - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Custom Home Assistant integration for Midea VRF air conditioning systems controlled via the **M-Control** cloud platform ([aircontrolbase.com](https://www.aircontrolbase.com)). Supports optional **local polling** from CCM21-i/CCM15 gateways for fast status updates.

## Features

- **Hybrid mode**: Fast local status polling (every 5s) + cloud control commands
- **Cloud-only mode**: Works without local access (polls every 60s)
- Auto-discovery of all AC units linked to your account
- Full climate entity support:
  - **HVAC modes**: Cool, Heat, Auto, Dry, Fan Only, Off
  - **Fan modes**: Auto, Low, Medium, High
  - **Swing mode**: On / Off
  - **Target temperature**: 16-30 C
  - **Current temperature** reading
- Automatic cloud-to-local address mapping
- Automatic session management with re-login on expiry
- Cloud fallback if local gateway becomes unreachable
- Spanish and English translations

## Requirements

- A Midea CCM21-i or CCM15 controller connected to your VRF system
- An active account at [aircontrolbase.com](https://www.aircontrolbase.com/login.html)
- Home Assistant 2024.1.0 or newer
- (Optional) Local network access to the gateway for fast polling

## Installation via HACS

1. Open HACS in Home Assistant
2. Click the 3-dot menu in the top right corner
3. Select **Custom repositories**
4. Add `https://github.com/DiraSmart/m-control-cloud-integration` and select **Integration**
5. Click **Add**
6. Search for "Midea M-Control" and install it
7. Restart Home Assistant

## Manual Installation

1. Copy the `custom_components/midea_mcontrol` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** > **Devices & Services**
2. Click **+ Add Integration**
3. Search for **Midea M-Control**
4. Enter your aircontrolbase.com email and password
5. (Optional) Enter the local IP of your CCM21-i/CCM15 gateway (e.g., `192.168.0.153`)
6. All AC units will be automatically discovered and added as climate entities

## How It Works

### Hybrid Mode (recommended)

When a local gateway IP is provided:
- **Status**: Polled locally via `POST /get_mbdata_all.jsn` every **5 seconds** (fast, LAN-only)
- **Control**: Sent via cloud API at `aircontrolbase.com` (reliable, authenticated)
- The integration automatically maps cloud device IDs to local addresses on startup

### Cloud-Only Mode

Without a local IP:
- Everything goes through the cloud API (polls every 60 seconds)

### API Endpoints

| Source | Endpoint | Purpose |
|---|---|---|
| Cloud | `POST /web/user/login` | Authentication |
| Cloud | `POST /web/userGroup/getDetails` | Fetch devices and states |
| Cloud | `POST /web/device/control` | Send control commands |
| Local | `POST /get_mbdata_all.jsn` | Fast status polling (7-byte hex protocol) |

## Troubleshooting

- **Cannot connect**: Ensure your Home Assistant instance has internet access
- **Invalid credentials**: Verify you can log in at [aircontrolbase.com](https://www.aircontrolbase.com/login.html)
- **Local unreachable**: Verify the gateway IP is correct and accessible from your HA network
- **Devices not showing**: Check that your CCM21-i/CCM15 controller is online and connected to the cloud
- **Slow updates**: Add the local gateway IP in the integration config for 5-second polling

## Credits

- Cloud API from the [homebridge-aircontrolbase](https://github.com/enudler/homebridge-aircontrolbase) plugin
- Local protocol from the [py-ccm15](https://github.com/ocalvo/py-ccm15) library and [Home Assistant CCM15 integration](https://www.home-assistant.io/integrations/ccm15/)
