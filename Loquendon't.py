import pyttsx3
import edge_tts
import asyncio
import re
import os
import sys
from pydub import AudioSegment

# --- Configuration ---
# NOTE: pydub requires FFmpeg to be installed on your system and accessible in PATH.
TEMP_DIR = "tts_temp_segments"
VOICE_CMD_PATTERN = re.compile(r'/voice=(\d+)', re.IGNORECASE)

# --- Asynchronous Helper for Edge-TTS (FIX) ---
async def _run_edge_tts_segment_save(text, voice_id, output_path):
    """Asynchronous function to encapsulate edge-tts communication."""
    communicate = edge_tts.Communicate(text, voice_id)
    await communicate.save(output_path)

class UnifiedTTSEngine:
    """
    Manages pyttsx3 (SAPI5/offline) and edge_tts (Online/Edge) engines
    and provides a unified list of available voices.
    """
    def __init__(self):
        print("Initializing TTS engines...")
        # We no longer store the engine, as we initialize it per-segment for reliability
        self.unified_voices = [] 
        self.pyttsx3_available = False

        # 1. Map pyttsx3 voices (Requires temporary engine init)
        self._map_pyttsx3_voices()

        # 2. Get edge-tts voices (Online voices)
        self._map_edge_tts_voices()

        if not self.unified_voices:
            print("\nFATAL: No voices found on this system (neither pyttsx3 nor edge_tts). Cannot proceed.", file=sys.stderr)
            sys.exit(1)

        print(f"Initialization complete. Found {len(self.unified_voices)} total voices.")

    def _map_pyttsx3_voices(self):
        """Initializes a temporary pyttsx3 engine to map voices, then stops it."""
        temp_engine = None
        try:
            temp_engine = pyttsx3.init()
            print("  - Fetching pyttsx3 (Offline) voices...")
            pyttsx3_voices = temp_engine.getProperty('voices')
            for voice in pyttsx3_voices:
                self.unified_voices.append({
                    'index': len(self.unified_voices),
                    'engine': 'pyttsx3',
                    'name': voice.name,
                    'id': voice.id,
                    'lang': voice.languages[0] if voice.languages else 'N/A'
                })
            self.pyttsx3_available = True
        except Exception as e:
            print(f"Warning: pyttsx3 initialization failed. Offline voices will not be available. Error: {e}", file=sys.stderr)
            self.pyttsx3_available = False
        finally:
            # Crucial: Stop the temporary engine immediately after fetching voices
            if temp_engine:
                temp_engine.stop()


    def _map_edge_tts_voices(self):
        """Maps edge_tts voices to the unified list."""
        # edge-tts list_voices is an async operation, but we run it once here
        # to set up the voice list.
        async def _fetch_edge_voices():
            return await edge_tts.list_voices()
            
        try:
            print("  - Fetching edge-tts (Online) voices...")
            # Use asyncio.run for robust blocking execution during initialization
            voices_list_raw = asyncio.run(_fetch_edge_voices())

            for voice in voices_list_raw:
                self.unified_voices.append({
                    'index': len(self.unified_voices),
                    'engine': 'edge-tts',
                    'name': voice['Name'],
                    'id': voice['ShortName'],
                    'lang': voice['Locale']
                })
        except Exception as e:
            print(f"Warning: edge-tts voice fetching failed. Online voices may be unavailable. Error: {e}", file=sys.stderr)

    def get_voice_by_index(self, index):
        """Retrieves a voice object by its unified index."""
        try:
            return self.unified_voices[index]
        except IndexError:
            return None

    def list_voices(self):
        """Prints the full list of unified voices."""
        print("\n--- Available TTS Voices ---")
        print(f"| {'ID':<3} | {'Engine':<10} | {'Name':<50} | {'Language':<10} |")
        print("|" + "-"*3 + "|" + "-"*10 + "|" + "-"*50 + "|" + "-"*10 + "|")
        for voice in self.unified_voices:
            name = voice['name'] if voice['engine'] == 'pyttsx3' else voice['id']
            # Truncate long names for clean display
            display_name = (name[:47] + '...') if len(name) > 50 else name.ljust(50)
            
            print(f"| {voice['index']:<3} | {voice['engine']:<10} | {display_name} | {voice['lang']:<10} |")
        print("----------------------------\n")

    def synthesize_segment(self, text, voice_index, base_output_path):
        """
        Synthesizes a single text segment using the correct engine. 
        Returns the final, correctly-named file path if successful, otherwise None.
        """
        voice = self.get_voice_by_index(voice_index)
        if not voice:
            print(f"Error: Voice ID {voice_index} not found. Skipping segment.", file=sys.stderr)
            return None

        # Determine the correct extension based on the engine
        ext = '.wav' if voice['engine'] == 'pyttsx3' else '.mp3'
        
        # Construct the final output path with the correct extension
        output_filepath = base_output_path + ext

        print(f"-> Synthesizing (Voice: {voice_index} - {voice['engine']}): '{text[:30].strip()}...' to {output_filepath}")
        print(f"   [DEBUG] Chosen Engine: {voice['engine']}, Extension: {ext}")

        if voice['engine'] == 'pyttsx3':
            if not self.pyttsx3_available:
                 print("Error: pyttsx3 engine is not available.", file=sys.stderr)
                 return None

            temp_engine = None
            try:
                # Initialize engine instance inside the function for segment
                temp_engine = pyttsx3.init()
                temp_engine.setProperty('voice', voice['id'])
                
                # pyttsx3 can only reliably save to WAV
                temp_engine.save_to_file(text, output_filepath)
                
                # This is the blocking call that executes the save
                temp_engine.runAndWait()
                
                # Check if file was created
                return output_filepath if os.path.exists(output_filepath) else None
            except Exception as e:
                print(f"Error synthesizing with pyttsx3: {e}", file=sys.stderr)
                return None
            finally:
                # Explicitly stop the driver to prevent the internal event loop from hanging
                if temp_engine:
                    temp_engine.stop()


        elif voice['engine'] == 'edge-tts':
            try:
                # Use asyncio.run on the async helper function to create a clean event loop
                asyncio.run(_run_edge_tts_segment_save(text, voice['id'], output_filepath))

                # Check if file was created
                return output_filepath if os.path.exists(output_filepath) else None
            except Exception as e:
                print(f"Error synthesizing with edge-tts: {e}", file=sys.stderr)
                return None

        return None # Should be unreachable

# --- Core Logic ---

def parse_input_file(input_filepath, default_voice_index):
    """
    Reads the input file and splits the content into text segments
    and associated voice IDs based on the /voice=ID command.
    """
    try:
        # Use a raw string for compatibility, though path strings should handle backslashes correctly here
        with open(input_filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: Input file not found at '{input_filepath}'", file=sys.stderr)
        return []
    except Exception as e:
         print(f"Error opening input file: {e}", file=sys.stderr)
         return []

    # Replace newlines with spaces for simpler parsing, but keep paragraph breaks
    content = content.replace('\n', ' ').replace('\r', '')

    # Split the text by the voice command, but keep the command in the list
    parts = VOICE_CMD_PATTERN.split(content)

    segments = []
    current_voice_index = default_voice_index

    i = 0
    while i < len(parts):
        part = parts[i].strip()

        if not part:
            i += 1
            continue

        if VOICE_CMD_PATTERN.match(f"/voice={part}"):
            # It's a voice ID (because re.split keeps the captured group at this index)
            try:
                current_voice_index = int(part)
                # Skip the captured group part and move to the next text segment
                i += 1
                continue
            except ValueError:
                # Should not happen if regex worked, but for safety
                i += 1
                continue
        else:
            # It's a text segment
            segments.append({
                'text': part, 
                'voice_index': current_voice_index
            })
            i += 1
            
    return segments

def process_and_concatenate(engine: UnifiedTTSEngine, input_file, output_file):
    """
    Handles the full pipeline: parsing, segment synthesis, and concatenation.
    """
    default_voice_index = 0
    segments = parse_input_file(input_file, default_voice_index)

    if not segments:
        print("No processable text segments found. Exiting.")
        return

    # 1. Setup temporary directory
    os.makedirs(TEMP_DIR, exist_ok=True)
    temp_files = []

    # 2. Process each segment
    print("\n--- Starting Segment Synthesis ---")
    
    successful_segments = 0
    for i, segment in enumerate(segments):
        # Base path without extension
        base_temp_path = os.path.join(TEMP_DIR, f"segment_{i}") 
        
        # Check if the voice index is valid
        if segment['voice_index'] >= len(engine.unified_voices):
            print(f"Warning: Voice ID {segment['voice_index']} is out of range. Using default voice (ID {default_voice_index}).", file=sys.stderr)
            segment['voice_index'] = default_voice_index

        # synthesize_segment returns the final, correctly-named file path (e.g., segment_i.mp3 or segment_i.wav)
        final_temp_path = engine.synthesize_segment(segment['text'], segment['voice_index'], base_temp_path)

        if final_temp_path:
            temp_files.append(final_temp_path)
            successful_segments += 1
        else:
            print(f"Failed to generate audio for segment {i}. Skipping.", file=sys.stderr)

    if successful_segments == 0:
        print("\nFailed to generate any audio segments. Aborting concatenation.", file=sys.stderr)
        return

    # 3. Concatenate audio files using pydub
    print("\n--- Starting Audio Concatenation ---")
    combined_audio = AudioSegment.empty()
    
    # Load and append all successfully generated temporary files
    for temp_path in temp_files:
        try:
            segment_audio = AudioSegment.from_file(temp_path) 
            combined_audio += segment_audio
        except Exception as e:
            print(f"Error loading temporary file {temp_path} for concatenation: {e}", file=sys.stderr)
            
    # 4. Export final file
    print(f"Exporting final file to '{output_file}'...")
    try:
        # Use the file extension to determine export format
        extension = os.path.splitext(output_file)[1].lower().strip('.')
        if not extension:
            output_file += ".wav"
            extension = "wav"

        combined_audio.export(output_file, format=extension)
        print(f"\nSUCCESS! Audio saved as '{output_file}'")
    except Exception as e:
        print(f"FATAL: Failed to export final audio file. Ensure FFmpeg is installed and accessible. Error: {e}", file=sys.stderr)

    # 5. Cleanup
    for temp_path in temp_files:
        os.remove(temp_path)
    os.rmdir(TEMP_DIR)
    print("Temporary files cleaned up.")


def main_menu(engine: UnifiedTTSEngine):
    """The main command-line interface menu."""
    while True:
        print("\n--- Loquendon't menu ---")
        print("1. List available voices with IDs")
        print("2. Process text file and generate audio (supports /voice=ID commands)")
        print("3. Exit")
        
        choice = input("Enter your choice (1-3): ").strip()

        if choice == '1':
            engine.list_voices()
        
        elif choice == '2':
            print("\n[Input/Output Configuration]")
            
            # Use strip('"') to remove surrounding double quotes, which are often 
            # included when copying paths with spaces from the file explorer.
            input_file = input("Enter the input text file path (e.g., input.txt): ").strip().strip('"')
            output_file = input("Enter the output audio file path MUST BE A .wav File (e.g., output.wav): ").strip().strip('"')

            if not input_file or not output_file:
                print("Input and output paths cannot be empty.")
                continue

            try:
                process_and_concatenate(engine, input_file, output_file)
            except Exception as e:
                print(f"An unexpected error occurred during processing: {e}", file=sys.stderr)
        
        elif choice == '3':
            print("Exiting Loquendon't.")
            break
        
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    # Ensure all necessary modules are available
    try:
        import pyttsx3
        import edge_tts
        from pydub import AudioSegment
    except ImportError:
        print("Required modules are missing. Please install them using:")
        print("pip install pyttsx3 edge-tts pydub")
        sys.exit(1)
        
    # Create a dummy input file for testing purposes if it doesn't exist
    test_file = "input.txt"
    if not os.path.exists(test_file):
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(
                f"Hello and welcome to the Multi-Voice Text-to-Speech System.\n\n"
                f"This entire application is running using local voices and online voices seamlessly.\n\n"
                f"/voice=1 This segment should be spoken by voice 1. It is likely a different gender or accent from the default voice.\n\n"
                f"/voice=0 We switch back to the default voice (voice 0) for this final thought. Enjoy your generated audio!"
            )
        print(f"NOTE: A sample input file ('{test_file}') has been created for demonstration.")


    tts_engine = UnifiedTTSEngine()
    if tts_engine.unified_voices:
        pass
    
    main_menu(tts_engine)