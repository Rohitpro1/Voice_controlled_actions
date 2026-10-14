import asyncio
import re
import speech_recognition as sr
from nikki_streams import SDK

# Keep your existing working values
SESSION_ID = "hlx573495851"
PHONE_ADDRESS = "192.168.29.101:3000"

# Initialize the Streams SDK
SDK.initialize(SESSION_ID)

# Microphone setup
recognizer = sr.Recognizer()
microphone = sr.Microphone()


def listen_for_command():
    """Listen through the Mac microphone and recognize speech."""
    with microphone as source:
        print("\nListening... Say a flashlight on/off command.")

        recognizer.adjust_for_ambient_noise(source, duration=0.5)

        audio = recognizer.listen(
            source,
            timeout=8,
            phrase_time_limit=10
        )

    return recognizer.recognize_google(audio).strip()


def classify_light_command(text):
    """Recognize common ways to ask for the flashlight to turn on or off."""
    command = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    command = re.sub(r"\s+", " ", command).strip()
    device = r"(?:flash\s*light|lights?)"
    before_device = rf"(?:the\s+|my\s+|phone\s+)?{device}"
    patterns = (
        ("on", rf"\b(?:turn|switch|power)\s+on\s+{before_device}\b"),
        ("off", rf"\b(?:turn|switch|power)\s+off\s+{before_device}\b"),
        ("on", rf"\b(?:turn|switch|power)\s+{before_device}\s+on\b"),
        ("off", rf"\b(?:turn|switch|power)\s+{before_device}\s+off\b"),
        ("on", rf"\b{device}\s+(?:is\s+)?on\b"),
        ("off", rf"\b{device}\s+(?:is\s+)?off\b"),
        ("on", rf"\b(?:activate|enable)\s+{before_device}\b"),
        ("off", rf"\b(?:deactivate|disable)\s+{before_device}\b"),
    )
    for state, pattern in patterns:
        if re.search(pattern, command):
            return state
    return None


def parse_voice_notification(text):
    """Parse a spoken notification command and return its title and message."""
    match = re.match(
        r"^send\s+(?:a\s+)?notification\b\s*(.*)$",
        text.strip(),
        re.IGNORECASE,
    )
    if not match:
        return None

    content = match.group(1).strip()
    if not content:
        return None

    titled = re.match(r"^title\s+(.+?)\s+message\s+(.+)$", content, re.IGNORECASE)
    if titled:
        title = titled.group(1).strip()
        message = titled.group(2).strip()
    else:
        title = "VoiceLight"
        message = re.sub(r"^message\s+", "", content, flags=re.IGNORECASE).strip()

    if not title or not message or len(title) > 80 or len(message) > 300:
        return None
    return title, message


async def main():
    device = SDK.create_device(
        PHONE_ADDRESS,
        lambda event: print("Connection:", event.data)
        if event.type == "statusChange"
        else None
    )

    try:
        print("Connecting to your phone...")
        await device.connect()

        print("Connected. Starting device tests.")

        # Test vibration
        try:
            print("\nTesting vibration...")
            await device.set_haptic()
            print("Vibration command sent.")
        except Exception as error:
            print("Vibration test failed:", error)

        # Test notification
        try:
            print("\nTesting notification...")
            await device.set_notification(
                "Streams Test",
                "Python command received"
            )
            print("Notification command sent.")
        except Exception as error:
            print("Notification test failed:", error)

        print("\nStartup checks finished. The flashlight will stay unchanged until you give a voice command.")
        print("Voice control is starting.")

        while True:
            try:
                command = await asyncio.to_thread(listen_for_command)
                print("Recognized:", command)

                action = classify_light_command(command)
                if action == "on":
                    print("Matched flashlight ON command.")
                    await device.set_light_status(True)
                    print("Flashlight ON command sent.")

                elif action == "off":
                    print("Matched flashlight OFF command.")
                    await device.set_light_status(False)
                    print("Flashlight OFF command sent.")

                elif re.match(r"^send\s+(?:a\s+)?notification\b", command, re.IGNORECASE):
                    notification = parse_voice_notification(command)
                    if notification is None:
                        print("Notification not sent. Say 'send notification' followed by a message.")
                        print("For a title, say 'send notification title [title] message [message]'.")
                    else:
                        title, message = notification
                        await device.set_notification(title, message)
                        print(f"Notification command sent. Title: {title}")

                else:
                    print("Command not recognized. Please try again.")

            except sr.WaitTimeoutError:
                print("No speech detected. Try again.")

            except sr.UnknownValueError:
                print("Sorry, I couldn't understand. Try again.")

            except sr.RequestError as error:
                print("Speech recognition error:", error)

            except Exception as error:
                print("Command error:", error)

    except KeyboardInterrupt:
        print("\nStopping the program...")

    except Exception as error:
        print("Connection or startup error:", error)

    finally:
        try:
            await device.disconnect()
            print("Disconnected.")
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram stopped.")
