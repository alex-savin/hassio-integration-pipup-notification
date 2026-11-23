# PiPup for Home Assistant

A [Home Assistant](https://www.home-assistant.io/) custom integration for
**[PiPup](https://github.com/alex-savin/android-pipup)**: pop-up notifications on
your Android TV. Send camera views, doorbell streams, text-to-speech alerts and
styled cards to the TV from any automation. TVs on your network are **discovered
automatically**.

> This is the Home Assistant companion to the PiPup Android TV app. You need the
> [PiPup app](https://github.com/alex-savin/android-pipup) installed and running on
> your Android TV first.

## Features

- 🔎 **Zero-config discovery**: TVs running PiPup are found automatically over mDNS.
- ⚡ **Instant state**: with PiPup 0.4.0 or newer the TV **pushes** every change
  (popup shown or closed, screen on or off, screensaver) to Home Assistant at once.
  It arrives as a `pipup_event`. Older apps are polled every 60 s.
- 📷 **Cameras by name**: give `camera_entity: camera.front_door` and Home Assistant
  sends the TV a signed link to its own camera feed, with a snapshot as the poster
  while the live view starts. The TV never needs the camera's address or password.
- 🔔 **Standard notify target**: `notify.send_message` with a title and message.
- 🎨 **Rich `pipup.send` service** with these options:
  - **Media**: images, live RTSP/HLS streams, web pages, **WebRTC (WHEP)** streams
    and a **grid of up to 9 cameras**, with a poster image while video starts.
  - **Sound and speech**: text-to-speech with a language, and a built-in chime or
    your own sound with a volume.
  - **Placement and look**: 9 positions, full screen, opacity, colors, borders,
    a progress bar, and entrance and exit animations.
- 🎛️ **Interactive buttons**: a press fires a **`pipup_button`** event. Each popup
  gets its own one-off token, so a press cannot be forged for another popup or TV.
- 🧹 **`pipup.dismiss`**: close one popup by id, or all of them.
- 📊 **Entities**:
  - connectivity, screen on or off, and popup on screen;
  - popups on screen and the last popup received;
  - a "Wake screen" and a "Dismiss popups" button.
- 🛠️ **Repairs**: if the TV loses "display over other apps" (no popup can appear),
  a repair notice shows how to grant it again.
- 🔐 **Token aware**: supply the device's auth token once and it is stored with the entry.
- 📐 **Blueprints**: an info-card script, and "appliance done" (washer, dryer and so on).
- 🌐 **Translated**: English and Brazilian Portuguese (pt-BR).

## Requirements

- Home Assistant **2025.2** or newer, with an **internal URL** the TV can reach
  (*Settings → System → Network*). Push, buttons and cameras all need it.
- The **PiPup** app on one or more Android TVs on the same network. Some features
  need a minimum app version:

| Feature | PiPup app |
|---|---|
| Push state, positions 5–8, `whep_uri`, `poster_uri`, opacity, sound volume, TTS language, wake screen | 0.4.0 |
| `grid`, `fullscreen`, `buffer_ms`, `decoder`, `poster_mode`, a wake that reports whether the screen came on | 0.5.0 |

The integration refuses positions 5–8, `whep` and `grid` on older apps, because those
would make an old app reject the whole notification. Other new options are ignored by
older apps.

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

- **Automatic:** Home Assistant shows a discovered **PiPup** device under
  *Settings → Devices & Services*. Click **Configure** to add it.
- **Manual:** *Settings → Devices & Services → Add Integration → PiPup*, then enter the
  TV's IP address (port defaults to `7979`). Provide the token only if you enabled
  authentication on the device.

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

### A camera

```yaml
action: pipup.send
target:
  entity_id: notify.pipup_living_room
data:
  title: "Front door"
  camera_entity: camera.front_door
  camera_mode: mjpeg      # mjpeg (default) · stream · snapshot
  media_width: 640
  duration: 30
```

| `camera_mode` | What the TV gets |
|---|---|
| `mjpeg` | Live MJPEG from Home Assistant's camera proxy, in a web view. Works with any camera. |
| `stream` | HLS from the [stream](https://www.home-assistant.io/integrations/stream/) integration, which must be set up. A few seconds behind live. |
| `snapshot` | One still image, uploaded to the TV. Buttons are not available with uploads. |

The links are signed and expire: after 24 h for a popup with a duration, after 30 days
for a sticky one (`duration: 0`).

### The fastest camera view: WebRTC (WHEP)

If you run [go2rtc](https://github.com/AlexxIT/go2rtc) (the Home Assistant add-on, or
the one built into Home Assistant on port 1984), its WHEP endpoint is usually well under
a second behind the camera:

```yaml
action: pipup.send
target:
  entity_id: notify.pipup_living_room
data:
  title: "Front door"
  whep_uri: "http://192.168.1.10:1984/api/webrtc?src=front_door"
  poster_uri: "http://192.168.1.10:1984/api/frame.jpeg?src=front_door"
  media_width: 640
  media_height: 360
```

A **grid** shows up to 9 of them (PiPup 0.5.0). All must come from the same go2rtc:

```yaml
action: pipup.send
target:
  entity_id: notify.pipup_living_room
data:
  fullscreen: true
  duration: 60
  grid:
    - "http://192.168.1.10:1984/api/webrtc?src=front_door"
    - uri: "http://192.168.1.10:1984/api/webrtc?src=driveway"
      label: Driveway
      poster: "http://192.168.1.10:1984/api/frame.jpeg?src=driveway"
```

### Other media

```yaml
action: pipup.send
target:
  entity_id: notify.pipup_living_room
data:
  title: "Front door"
  message: "Someone is at the door"
  tts: "Someone is at the front door"
  tts_language: en-US
  sound: default            # the built-in chime, or a URL
  sound_volume: 0.5
  duration: 20
  position: 5               # 0 top right · 1 top left · 2 bottom right · 3 bottom left · 4 center
                            # 5 top center · 6 bottom center · 7 center left · 8 center right
  opacity: 0.9
  corner_radius: 16
  border_color: "#FF34D399"
  border_width: 3
  show_progress: true
  video_uri: "rtsp://user:pass@camera.local:554/stream"   # or image_uri, web_uri
  buffer_ms: 300            # lower RTSP delay (PiPup 0.5.0)
  media_width: 480
  media_position: 2         # 0 top · 1 bottom · 2 left · 3 right
  animation_type: slide     # none · fade · slide · scale
```

Credentials in the URL (`user:pass@host`) work for RTSP, and from PiPup 0.5.0 also for
`http(s)://` video and image URLs. For Home Assistant cameras, `camera_entity` avoids
credentials altogether.

### Buttons

Add up to **three** remote-operable buttons. When a popup has `buttons`, the integration
points its callback at Home Assistant, so a press fires a **`pipup_button`** event with
no webhook to set up. Use `duration: 0` to keep the popup up until a button is pressed.

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

**OK** activates the focused button; **BACK** dismisses without a press.

> **Security:** each popup with buttons gets its own token in the callback URL. The token
> accepts one press of a button that was on that popup, and expires with it (sticky
> popups after 7 days). The event's `popup_id`, `button` and `label` come from what Home
> Assistant sent, not from the TV's request. The webhook only accepts requests from your
> local network. For locks and garage doors, also constrain the automation on `device_id`.

### Close a popup

```yaml
action: pipup.dismiss
target:
  entity_id: notify.pipup_living_room
data:
  id: doorbell     # leave out to close every popup
```

## Entities

| Entity | Description |
|---|---|
| `notify.pipup_<name>` | Notify target; also the target for `pipup.send` and `pipup.dismiss`. |
| `binary_sensor.pipup_<name>_connectivity` | On while the TV answers. Attributes: `version`, `active`, `count`, `auth_enabled`, `push`. |
| `binary_sensor.pipup_<name>_screen` | On while the TV screen is on. Attribute `screensaver`. |
| `binary_sensor.pipup_<name>_popup_on_screen` | On while any popup is shown. Attribute `popup_ids`. |
| `binary_sensor.pipup_<name>_overlay_permission` | Problem sensor: on when PiPup may not draw over other apps. |
| `sensor.pipup_<name>_popups_on_screen` | Number of popups on screen; attribute `popups` with each one's details. |
| `sensor.pipup_<name>_last_popup` | Id of the last popup the TV received; position, media and so on as attributes. |
| `button.pipup_<name>_wake_screen` | Turns the screen on and ends the screensaver. |
| `button.pipup_<name>_dismiss_popups` | Closes every popup. |

The device page shows the PiPup version and the TV model.

## Events

| Event | Fired when | Data |
|---|---|---|
| `pipup_event` | The TV pushes a change (PiPup 0.4.0+) | `device_id`, `entry_id`, `event`, and `popup_id` and `reason` where they apply |
| `pipup_button` | A popup button is pressed | `device_id`, `entry_id`, `popup_id`, `button`, `label` |
| `pipup_callback` | A popup with buttons is shown or dismissed | `device_id`, `entry_id`, `popup_id`, `event` (`shown`/`dismissed`) |

`pipup_event` values:
- `started`: the app (re)started;
- `popup_shown`, `popup_updated`, `popup_removed`, where `reason` is one of:
  - `expired`, `cancelled`, `button` or `back`;
  - `replaced`;
  - `evicted`, when too many popups were on screen;
  - `error`, when the media failed fatally;
  - `service_stopped`;
- `screen_on`, `screen_off`, `screensaver_started`, `screensaver_stopped`.

## Blueprints

[![Import the info card blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Falex-savin%2Fhassio-integration-pipup-notification%2Fblob%2Fmain%2Fblueprints%2Fscript%2Fpipup_info_card.yaml)
**Info card** (script): call it with a title and message. Pass a `card_id` to update the
same card in place.

[![Import the appliance done blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Falex-savin%2Fhassio-integration-pipup-notification%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fpipup_appliance_done.yaml)
**Appliance done** (automation): watches a power sensor and shows a card when the
appliance has finished. A helper remembers the running state, and a periodic check
catches a finish that happened while Home Assistant was restarting. Optionally it only
shows the card while a TV screen is on; if the screen is off, the card waits until it
comes on.

## Diagnostics

*Settings → Devices & Services → PiPup → the TV → Download diagnostics* gives the TV's
last status and push state. The token and webhook ids are redacted.

## License

[MIT](LICENSE).
