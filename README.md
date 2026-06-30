# Wallbox BLE for Home Assistant

Local control of a Wallbox charger over Bluetooth Low Energy (BLE) — no cloud, no
WiFi and no MyWallbox account required. Works with the BLE-only **Pulsar** as well
as the **Pulsar Plus**.

## Supported hardware / BLE profiles

Wallbox shipped several BLE radio modules across hardware revisions. They all
speak the same `EaE`+JSON application protocol but expose different GATT UUIDs.
This integration auto-detects the profile on connect:

| Profile | Devices | Service UUID |
| --- | --- | --- |
| `zentri` | original **Pulsar** (no WiFi) and newer units | `175f8f23-…` |
| `bgexpress` | **Pulsar Plus** | `331a36f5-…` |

No BLE pairing/bonding is used — the charger is controlled over an unauthenticated
GATT connection, exactly like the official app. (Zentri-based units are additionally
switched into "stream" mode and the session is logged in with the charger's own
user id, both handled automatically.)

## Implemented features
 - charger status
 - lock / unlock
 - charge current
 - start / stop charging (only available while charging/paused)

## Requirements
 - Home Assistant with a working Bluetooth integration — either a local adapter
   in range of the charger, or an [ESPHome Bluetooth proxy](https://esphome.io/components/bluetooth_proxy.html).

## Installation (HACS)
1. HACS → ⋮ → *Custom repositories* → add this repository as an *Integration*.
2. Install **Wallbox BLE** and restart Home Assistant.
3. The charger (advertised as `WBxxxxxx`) is auto-discovered under
   *Settings → Devices & Services*; add it. No PIN is needed.

## Notes
 - Make sure the charger is within Bluetooth range of the HA host or a BT proxy.
 - The charger accepts a single BLE connection at a time; if the Wallbox phone app
   is connected it may briefly block Home Assistant (and vice-versa).