
import asyncio
import speech_recognition as sr
from nikki_streams import SDK

# Keep the actual values from your working main.py
SESSION_ID = "hlx573495851"
PHONE_ADDRESS = "192.168.29.101:3000"

SDK.initialize(SESSION_ID)

recognizer = sr.Recognizer()
microphone = sr.Microphone()


def listen_for_command():
    """Listen to the Mac microphone and convert speech to text."""
    with microphone as source:
        print("\nListening... Say 'Turn on the light' or 'Turn off the light'.")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(
            source,
            timeout=8,
            phrase_time_limit=5
        )

    return recognizer.recognize_google(audio).lower()



async def main():
    device = SDK.create_device(
        PHONE_ADDRESS,
        lambda event: print("Connection:", event.data)
        if event.type == "statusChange"
        else None
    )

    try:
        await device.connect()

        print("Testing vibration...")
        await device.set_haptic()

        print("Testing notification...")
        await device.set_notification(
            "Streams Test",
            "Python command received"
        )

        await asyncio.sleep(2)

        print("Testing flashlight...")
        await device.set_light_status(True)
        await asyncio.sleep(3)
        await device.set_light_status(False)

        print("Tests finished.")

        while True:
            try:
                command = await asyncio.to_thread(listen_for_command)
                print("Recognized:", command)

                if "turn on the light" in command:
                    await device.set_light_status(True)
                    print("Flashlight ON")

                elif "turn off the light" in command:
                    await device.set_light_status(False)
                    print("Flashlight OFF")

                else:
                    print("Command not recognized. Try the exact phrase.")

            except sr.WaitTimeoutError:
                print("No speech detected. Try again.")

            except sr.UnknownValueError:
                print("Sorry, I couldn't understand. Try again.")

            except sr.RequestError as error:
                print("Speech recognition service error:", error)
                await asyncio.sleep(1)

    finally:
        await device.disconnect()
