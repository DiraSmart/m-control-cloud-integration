# Midea M-Control Cloud - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Custom Home Assistant integration for Midea VRF air conditioning systems controlled via the **M-Control** cloud platform ([aircontrolbase.com](https://www.aircontrolbase.com)).

## Features

- Cloud-based control (no local network access to CCM15 needed)
- Auto-discovery of all AC units linked to your account
- Full climate entity support:
  - **HVAC modes**: Cool, Heat, Auto, Dry, Fan Only, Off
  - **Fan modes**: Auto, Low, Medium, High
  - **Swing mode**: On / Off
  - **Target temperature**: 16-30 C
  - **Current temperature** reading
- Automatic session management with re-login on expiry
- Optimistic state updates for responsive UI
- Spanish and English translations

## Requirements

- A Midea CCM15 controller connected to your VRF system
- An active account at [aircontrolbase.com](https://www.aircontrolbase.com/login.html)
- Home Assistant 2024.1.0 or newer

## Installation via HACS

1. Open HACS in Home Assistant
2. Click the 3-dot menu in the top right corner
3. Select **Custom repositories**
4. Add the repository URL and select **Integration** as the category
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
5. All AC units will be automatically discovered and added as climate entities

## How It Works

This integration communicates with the Midea cloud server at `aircontrolbase.com` using the same API as the M-Control mobile app. It polls for device states every 30 seconds and sends control commands when you adjust settings.

### API Endpoints Used

| Endpoint | Purpose |
|---|---|
| `POST /web/user/login` | Authentication |
| `POST /web/userGroup/getDetails` | Fetch all devices and states |
| `POST /web/device/control` | Send control commands |

## Troubleshooting

- **Cannot connect**: Ensure your Home Assistant instance has internet access
- **Invalid credentials**: Verify you can log in at [aircontrolbase.com](https://www.aircontrolbase.com/login.html)
- **Devices not showing**: Check that your CCM15 controller is online and connected to the cloud

## Credits

- API reverse-engineered from the [homebridge-aircontrolbase](https://github.com/enudler/homebridge-aircontrolbase) plugin
- Inspired by the official [Home Assistant CCM15 integration](https://www.home-assistant.io/integrations/ccm15/) (local polling)
