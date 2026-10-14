# VoiceLight

VoiceLight lets your Mac send commands to your phone through the Nikki Streams app. You can use either the website or the original `main.py` program. Both use the same phone connection, so **run only one at a time**.

## Before you start

- Keep the Nikki Streams app open on your phone.
- Connect the phone and Mac to the same Wi-Fi network.
- Allow Terminal (or the app running Python) to use the Mac microphone if you want voice control.
- Keep the Mac connected to the internet for speech recognition.

## Option 1: Use the website

### Start it

1. Open Terminal.
2. Copy and run these commands:

   ```sh
   cd ~/Desktop/Stream-IoT-Projects
   source .venv/bin/activate
   python web_server.py
   ```

3. In your Mac browser, open **http://127.0.0.1:8000/**. Do not open `index.html` directly from Finder; the website needs the Python program running.
4. Check the status at the top. If it says the phone is disconnected, check Nikki Streams and Wi-Fi, then press **Reconnect phone**.

Keep the Terminal window open while using the website. To stop it, click the Terminal window and press **Control+C**.

### What is on the website

- **Phone light:** buttons to request the flashlight turn on or off.
- **Voice control:** press **Start**, speak a command, and press **Stop** when finished.
- **Notification:** enter a title and message, then press **Send notification**.
- **Notification history:** shows the title, full message, time, and whether it was sent from the website or by voice. It keeps up to 500 entries while the website's Python program is running. The list clears when that program stops.
- **Activity:** shows connection changes, recognized voice commands, and recent results or errors.

For spoken flashlight and notification commands, use the examples in **Voice commands** below. The notification form also accepts text, including numbers.

## Option 2: Use `main.py` in Terminal

Use this option when you want the original program without the website. First stop the website program with **Control+C**. Then run:

```sh
cd ~/Desktop/Stream-IoT-Projects
source .venv/bin/activate
python main.py
```

`main.py` connects to the phone, sends a startup vibration and a test notification, and then listens through the Mac microphone. **It does not turn the flashlight on at startup.** Say one short command when Terminal shows **Listening**. Press **Control+C** to stop.

`main.py` prints notification commands it sends in Terminal. It does not keep a notification history list. Use the website if you want to see a list of sent notification messages.

## Voice commands

Voice control uses the Mac's microphone. Start it first: press **Start** on the website, or run `main.py` and wait for **Listening** in Terminal. Then say one of the phrases below. You do not need to use the exact same wording; these are examples the program understands.

### Turn the flashlight on

- “Turn on the light”
- “Turn on flashlight”
- “Turn the light on”
- “Turn light on”
- “Light on” or “Flashlight on”
- “Switch on the light”
- “Enable the flashlight”

### Turn the flashlight off

- “Turn off the light”
- “Turn off flashlight”
- “Turn the light off”
- “Turn light off”
- “Light off” or “Flashlight off”
- “Switch off the light”
- “Disable the flashlight”

### Send a notification by voice

Say **“Send notification”** followed by your message. The title will be **VoiceLight**.

Example: “Send notification pick up milk”.

For your own title, say:

> Send notification title [your title] message [your message]

Example: “Send notification title Reminder message Take your keys”.

Speak clearly and keep messages short. The program converts your speech to text using Google's speech recognition service, so it may occasionally hear a different word. Check **Last heard** on the website or the **Recognized** line in Terminal.

## What the flashlight status means

The Nikki Streams tools used by this project can send an ON or OFF request, but they do not report the phone's actual flashlight state back to the Mac. On the website, **Last requested** means the last command the Mac sent; it is not a confirmation that the phone applied it.

## If something does not work

- **Website says “Backend unavailable”:** make sure `python web_server.py` is still running in Terminal. Open **http://127.0.0.1:8000/**, not the `index.html` file.
- **Phone says disconnected:** keep Nikki Streams open on the phone, check that the Mac and phone are on the same Wi-Fi, then press **Reconnect phone** on the website. If the phone's network address changed, the address in `web_server.py` may need updating.
- **No voice command is heard:** check microphone permission for Terminal in macOS System Settings. Make sure Terminal prints **Listening**, speak clearly, and check the recognized words.
- **Speech recognition error:** check the Mac's internet connection. Speech-to-text uses Google's recognition service.
- **Port 8000 is busy:** another program may already be using it. Stop that program before starting `web_server.py` again.
- **Do not run both programs together:** stop `web_server.py` before running `main.py`, or stop `main.py` before starting the website. They cannot share one phone session at the same time.

## For developers

The page files are `index.html`, `style.css`, and `script.js`. `web_server.py` serves those files and sends browser requests to the Nikki Streams SDK. The server listens only on this Mac at `127.0.0.1:8000`.

The main browser API routes are:

- `GET /api/status` — connection and voice status.
- `GET /api/logs` — recent activity.
- `GET /api/notifications` — notification history for the current server run.
- `POST /api/flashlight` — request flashlight ON or OFF.
- `POST /api/notification` — send a title and message.
- `POST /api/voice/start` and `POST /api/voice/stop` — control voice listening.
- `POST /api/reconnect` — retry the phone connection.

The existing `main.py` and `.venv` are kept in the project. The website reads the SDK session setting from `main.py` without importing or changing that program.
