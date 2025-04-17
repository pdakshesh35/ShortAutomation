import moviepy.editor as mp
import speech_recognition as sr
from pydub import AudioSegment
import os
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import urllib.request
import tempfile

class VideoSubtitleGenerator:
    def __init__(self, video_path, output_path, font_url="https://fonts.google.com/download?family=Montserrat"):
        """Initialize the subtitle generator with video path, output path, and font URL."""
        self.video_path = video_path
        self.output_path = output_path
        self.font_path = self._download_font(font_url)
        self.video = mp.VideoFileClip(video_path)
        self.audio_path = "temp_audio.wav"
        self.recognizer = sr.Recognizer()

    def _download_font(self, font_url):
        """Download a font from a URL and return the path to the TTF file."""
        temp_dir = tempfile.gettempdir()
        font_path = os.path.join(temp_dir, "Montserrat-Bold.ttf")
        
        # For simplicity, we'll assume the font is directly accessible or manually placed
        # In a real scenario, you'd need to handle font downloading and extraction
        # Here, we'll use a placeholder path; ensure Montserrat-Bold.ttf is available
        if not os.path.exists(font_path):
            raise FileNotFoundError("Please ensure Montserrat-Bold.ttf is available in the temp directory.")
        return font_path

    def _extract_audio(self):
        """Extract audio from the video and save as WAV."""
        audio = self.video.audio
        audio.write_wav(self.audio_path)
        audio.close()

    def _transcribe_audio(self):
        """Transcribe audio with word-level timestamps."""
        audio = AudioSegment.from_wav(self.audio_path)
        # Split audio into chunks for better transcription accuracy
        chunk_length_ms = 60000  # 1 minute chunks
        chunks = [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
        
        words = []
        current_time = 0

        for i, chunk in enumerate(chunks):
            chunk_path = f"temp_chunk_{i}.wav"
            chunk.export(chunk_path, format="wav")
            
            with sr.AudioFile(chunk_path) as source:
                audio_data = self.recognizer.record(source)
                try:
                    # Use Google Speech Recognition (requires internet)
                    result = self.recognizer.recognize_google(audio_data, show_all=True)
                    if 'alternative' in result:
                        for alt in result['alternative']:
                            if 'words' in alt:
                                for word_info in alt['words']:
                                    word = word_info['word']
                                    start_time = float(word_info['start_time']) + current_time
                                    end_time = float(word_info['end_time']) + current_time
                                    words.append((word, start_time, end_time))
                except sr.UnknownValueError:
                    print(f"Chunk {i} could not be transcribed.")
                except sr.RequestError as e:
                    print(f"Transcription error in chunk {i}: {e}")
            
            current_time += chunk_length_ms / 1000.0
            os.remove(chunk_path)
        
        return words

    def _create_subtitle_clip(self, text, start_time, end_time, font_size=60):
        """Create a subtitle clip with the given text and timing."""
        # Create a blank image for text
        img = Image.new('RGBA', (self.video.w, 100), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Load the font
        font = ImageFont.truetype(self.font_path, font_size)
        
        # Calculate text size and position
        text_width, text_height = draw.textsize(text, font=font)
        text_x = (self.video.w - text_width) // 2
        text_y = 10
        
        # Draw text with a slight shadow for style
        draw.text((text_x + 2, text_y + 2), text, font=font, fill=(0, 0, 0, 255))  # Shadow
        draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))  # Main text
        
        # Convert PIL image to MoviePy clip
        img_array = np.array(img)
        clip = mp.ImageClip(img_array).set_start(start_time).set_duration(end_time - start_time)
        clip = clip.set_position(('center', self.video.h - 120))  # Position at bottom
        return clip

    def add_subtitles(self):
        """Add synchronized subtitles to the video."""
        # Extract and transcribe audio
        self._extract_audio()
        words = self._transcribe_audio()
        
        # Create subtitle clips
        subtitle_clips = []
        for word, start_time, end_time in words:
            clip = self._create_subtitle_clip(word, start_time, end_time)
            subtitle_clips.append(clip)
        
        # Combine video with subtitles
        final_video = mp.CompositeVideoClip([self.video] + subtitle_clips)
        
        # Write output video
        final_video.write_videofile(self.output_path, codec="libx264", audio_codec="aac")
        
        # Clean up
        self.video.audio.close()
        self.video.close()
        if os.path.exists(self.audio_path):
            os.remove(self.audio_path)

    def __del__(self):
        """Clean up resources."""
        if hasattr(self, 'video') and self.video:
            self.video.close()
        if hasattr(self, 'audio_path') and os.path.exists(self.audio_path):
            os.remove(self.audio_path)

# Example usage:
# if __name__ == "__main__":
#     generator = VideoSubtitleGenerator("input.mp4", "output_with_subtitles.mp4")
#     generator.add_subtitles()