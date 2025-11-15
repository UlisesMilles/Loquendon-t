# Loquendon't
OpenSoucre TTS script that ONLY WORKS ON WINDOWS

Hi there! This is a crappy TTS script coded in python in one evening.
Initially I was just going to delete it after using it for what I wanted it, but then I said, hey, I don't think there are many TTS scripts in python out there. So here it is.

# How to run it
you will need python to run the script (I used python 3.12 to make it, but any newer version should do the trick)
you will need the following libraries: pyttsx3, edge-tts and pydub. Wich can be installed with the pip command.
```pip install pyttsx3 edge-tts pydub```
You will also need to have FFMPEG installed and added to PATH (google how to do it).
Download the repo, and save it into whatever folder.
Open the cmd (If you want to use powershell rename the file to remove the ' because for whatever reason powershell doesn't like it) and ```cd``` into the folder you saved the script.
Once there, type ```python.exe ./Loquendon't.py``` the script will run.
When the program loads, if it does not exist, a file called input.txt will be created. This is a demo file, wich you can use to test how the program works.
Input ```1``` to see a list of all avilable voices with it's IDs, I recommend copying the list that the progam gives you into notepad or something for future reference.
Choose option ```2``` to use the program. The program will ask for THE FULL PATH of the input text file and then THE FULL PATH of the output wav file (note that the output wav file will be created automatically when the script finishes running).
Once you have correctly inputed both input and output files, the program will start running. 
If the input file is long the program may appear like is doing nothing, but IT IS. Just let it do it's thing.
Once the scrip finishes running, you will have your output file ready to go.

# Input file structure
The input file doesn't have a defined structure, but you can use just one command in the input file wich is ```/voice=VoiceId``` this command can be inputed anywere in the file but it has to be by it self in a new line, nothing can be before nor after te command in the same line. 
The ```VoiceId``` parameter can be any id you got when you selected option ```1``` while running the program.

# Warning
Warning, this program will most likely not be mantained, so, as you can see, there is no lisenceing whatsoever.
So you have full permission to do whatever you want with this program, I would appretiate if you gave me credit for the program. But if not, it's ok.
