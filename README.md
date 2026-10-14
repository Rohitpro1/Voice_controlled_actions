VOICELIGHT

VoiceLight lets a Mac send flashlight commands and notifications to a phone through the Nikki Streams app. You can use the website or the original Python program. Run only one of them at a time.

WHAT IT CAN DO

- Request that the phone flashlight turn on or off.
- Use the Mac microphone to speak flashlight commands.
- Send phone notifications from the website or by voice.
- Show whether the phone is connected.
- Show notification titles, messages, times, and sources during the current website session.

BEFORE YOU START

- Keep Nikki Streams open on the phone.
- Connect the Mac and phone to the same Wi-Fi network.
- For voice control, allow microphone access for Terminal and keep the Mac online. Speech-to-text uses Google's recognition service.
- Use the existing Python environment in the .venv folder.
- Do not run web_server.py and main.py at the same time. They share the phone connection.

USE THE WEBSITE

1. Open Terminal.
2. Enter these commands:

   cd ~/Desktop/Stream-IoT-Projects
   source .venv/bin/activate
   python web_server.py

3. Keep Terminal open. In a browser on the same Mac or Windows open:

   http://127.0.0.1:8000/

4. Check the connection status. If the phone is disconnected, check Nikki Streams and Wi-Fi, then select Reconnect phone.
5. Use the flashlight buttons, notification form, or voice controls.

The Python program serves the website and connects it to the phone. Do not open index.html directly from Finder or start VS Code Live Server. To stop the website, press Control+C in the Terminal window running web_server.py.

WEBSITE FEATURES

- Phone light: sends an ON or OFF request.
- Voice control: select Start, speak, and select Stop when finished.
- Notification: enter a title and message, then select Send notification. Text and numbers are accepted.
- Notification history: lists up to 500 messages from the current run, with title, message, time, and source. The list clears when the Python service stops.
- Activity: shows connection changes, recognized speech, and recent results or errors.

The SDK cannot report the flashlight's actual state. “Last requested” means the last light command the Mac sent; it does not confirm the phone applied it.

RUN THE ORIGINAL PROGRAM

To use main.py without the website, stop web_server.py with Control+C, then run:

   cd ~/Desktop/Stream-IoT-Projects
   source .venv/bin/activate
   python main.py

main.py sends a startup vibration and a test notification, then starts listening. It does not turn the flashlight on at startup. When Terminal says Listening, speak a command. Press Control+C to stop. main.py prints notification commands in Terminal but does not keep a notification history list.

VOICE COMMANDS

Start voice control first. On the website select Start. In main.py wait until Terminal says Listening. Then say one short phrase.

Turn the flashlight on:
- Turn on the light
- Turn on flashlight
- Turn the light on
- Turn light on
- Light on or flashlight on
- Switch on the light
- Enable the flashlight

Turn the flashlight off:
- Turn off the light
- Turn off flashlight
- Turn the light off
- Turn light off
- Light off or flashlight off
- Switch off the light
- Disable the flashlight

Send a notification by voice:
- Say “Send notification” and then your message. The title will be VoiceLight. Example: “Send notification pick up milk”.
- To choose a title, say “Send notification title Reminder message Take your keys”.

The notification title can be up to 80 characters and the message up to 300 characters. Speak clearly; speech recognition can mishear words. On the website check Last heard. In Terminal check the Recognized line.

IF SOMETHING DOES NOT WORK

- Backend unavailable: check that web_server.py is still running. Open http://127.0.0.1:8000/ rather than the HTML file.
- Phone disconnected: keep Nikki Streams open, check that the Mac and phone share Wi-Fi, then select Reconnect phone. If the phone's network address changed, update it in web_server.py.
- Voice control cannot hear you: allow microphone access for Terminal in macOS System Settings. Confirm the website or Terminal says Listening.
- Speech recognition error: check the Mac's internet connection.
- Port 8000 is busy: stop the other program using the port before restarting web_server.py.
- Do not run the website and main.py together. Stop one before starting the other.

PROJECT FILES

index.html: website content and controls.
style.css: website appearance and mobile layout.
script.js: website interactions.
web_server.py: website service and phone connection.
main.py: standalone Python voice-control program.
.venv/: existing Python environment and packages.

The website reads the existing SDK session setting from main.py but does not show it in the browser. Keep local connection details private when sharing the project.
