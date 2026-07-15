# PiPup for Home Assistant

A [Home Assistant](https://www.home-assistant.io/) custom integration for
**[PiPup](https://github.com/alex-savin/android-pipup)** — pop-up notifications on
your Android TV. Send camera snapshots, doorbell streams, text-to-speech alerts and
styled overlays to the TV from any automation, with **automatic discovery** of the
TVs on your network.

> This is the Home Assistant companion to the PiPup Android TV app. You need the
> [PiPup app](https://github.com/alex-savin/android-pipup) installed and running on
> your Android TV first.

## Features

- 🔎 **Zero-config discovery** — TVs running PiPup are found automatically over mDNS.
- 🔔 **Standard notify target** — `notify.send_message` with a title and message.
- 🎨 **Rich `pipup.send` service** — images, **live RTSP/HLS camera streams**, web
  pages, text-to-speech, sound, colors, borders, progress, stacking, **media
  positioning** (top/bottom/left/right + alignment), and **entrance/exit animations**.
- 🎛️ **Interactive buttons** — add remote-operable buttons to a popup; a press fires a
  **`pipup_button`** event (carrying the TV's `device_id`) so an automation can react —
  unlock a door, acknowledge an alert, and so on. No webhook wiring required.
- ♻️ **Update-in-place** — reuse a popup `id` to refresh it without restarting a live
  stream; **`urgency`** presets; **`muted`** media; per-popup **button colors**.
- 🔐 **Token aware** — supply the device's auth token once; it's stored with the entry.
- 📶 **Connectivity sensor** — a `binary_sensor` per TV showing whether it's reachable,
  with the PiPup version and active-popup count as attributes.

## Requirements

- Home Assistant **2024.11** or newer.
- The **PiPup** app running on one or more Android TVs on the same network.

## Installation

### HACS (recommended)

1. HACS → **Integrations** → ⋮ → **Custom repositories**.
2. Add `https://github.com/alex-savin/hassio-integration-pipup-notification` with
   category **Integration**.
3. Install **PiPup**, then restart Home Assistant.

### Manual

Copy `custom_components/pipup` into your Home Assistant `config/custom_components/`
directory and restart.

## Setup

- **Automatic:** Home Assistant will show a discovered **PiPup** device under
  *Settings → Devices & Services*. Click **Configure** to add it.
- **Manual:** *Settings → Devices & Services → Add Integration → PiPup*, then enter the
  TV's IP address (port defaults to `7979`). Provide the token only if you enabled
  authentication on the device.

Each TV becomes a **device** with a `notify` entity and a connectivity `binary_sensor`.

## Usage

### Simple notification

```yaml
action: notify.send_message
target:
  entity_id: notify.pipup_living_room
data:
  title: "Front door"
  message: "Someone is at the door"
```

### Rich notification (`pipup.send`)

```yaml
action: pipup.send
target:
  entity_id: notify.pipup_living_room
data:
  title: "Front door"
  message: "Someone is at the door"
  tts: "Someone is at the front door"
  duration: 20
  position: 0
  corner_radius: 16
  border_color: "#FF34D399"
  border_width: 3
  show_progress: true
  image_uri: "https://camera.local/snapshot.jpg"
  media_width: 480
  media_position: 2          # 0 top · 1 bottom · 2 left · 3 right
  title_alignment: 1         # 0 left · 1 center · 2 right
  animation_type: slide      # none · fade · slide · scale
  animation_duration: 250
```

For a **live camera stream**, use `video_uri` with an RTSP or HLS URL (H.264):

```yaml
action: pipup.send
target:
  entity_id: notify.pipup_living_room
data:
  title: "Front door"
  video_uri: "rtsp://user:pass@camera.local:554/stream"
  media_width: 640
  duration: 60
```

### Buttons

Add up to **three** remote-operable buttons. When you include `buttons`, the integration
automatically points the popup's callback at Home Assistant, so a press fires a
**`pipup_button`** event — no webhook to set up. Use `duration: 0` to keep the popup up until
a button is pressed.

```yaml
action: pipup.send
target:
  entity_id: notify.pipup_living_room
data:
  title: "Front door"
  message: "Someone is at the door"
  duration: 0
  buttons:
    - id: unlock
      label: "Open the door"
    - id: ignore
      label: "Dismiss"
  button_color: "#1565C0"          # optional; label auto-contrasts
```

React to the press in an automation. The event data includes `device_id` (which TV),
`button` (the pressed button's `id`), `label`, and `popup_id`:

```yaml
automation:
  - alias: "Unlock the door from the TV popup"
    triggers:
      - trigger: event
        event_type: pipup_button
        event_data:
          button: unlock
    actions:
      - action: lock.unlock
        target:
          entity_id: lock.front_door
```

> Filter on `device_id` too if several TVs can show the same button, so only the TV you
> acted on triggers. **OK** activates the focused button; **BACK** dismisses without a press.
>
> **Security:** the callback endpoint that produces these events is unauthenticated (the TV
> can't log in to Home Assistant), so each callback URL carries a per-TV secret and forged
> requests are rejected. Still, for anything sensitive (locks, garage doors) constrain the
> automation on `device_id` as well, and keep Home Assistant off the public internet.

### In an automation

```yaml
automation:
  - alias: "Doorbell to TV"
    triggers:
      - trigger: state
        entity_id: binary_sensor.front_doorbell
        to: "on"
    actions:
      - action: pipup.send
        target:
          entity_id: notify.pipup_living_room
        data:
          title: "Front door"
          message: "Someone is at the door"
          tts: "Someone is at the front door"
          image_uri: "{{ states.camera.front_door.attributes.entity_picture }}"
```

## Entities

| Entity | Description |
|---|---|
| `notify.pipup_<name>` | Notify target; also the target for the `pipup.send` service. |
| `binary_sensor.pipup_<name>_connectivity` | On when the TV's PiPup server is reachable. Attributes: `version`, `active`, `count`, `auth_enabled`. |

## Events

| Event | Fired when | Data |
|---|---|---|
| `pipup_button` | A popup button is pressed on the TV | `device_id`, `entry_id`, `popup_id`, `button`, `label` |
| `pipup_callback` | A popup is shown or dismissed | `device_id`, `entry_id`, `popup_id`, `event` (`shown`/`dismissed`) |

## Status

Contributions welcome. Tracks the [PiPup app](https://github.com/alex-savin/android-pipup)
`0.3.0` feature set (buttons, update-in-place, urgency, muted media); see the app for the
device side and its HTTP API reference.

## License

[MIT](LICENSE).
