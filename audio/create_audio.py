from gtts import gTTS

text = """
Hello.

This is RJ Technologies.

Please press 1 to confirm.

Thank you.
"""

tts = gTTS(text=text, lang="en")

tts.save("audio/welcome.mp3")

print("MP3 Created Successfully")