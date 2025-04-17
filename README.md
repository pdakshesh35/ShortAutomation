# YouTube Shorts News Video Generator

This project is a FastAPI-based application that automates the creation of engaging YouTube Shorts-style news videos. It fetches news articles, generates a 2-minute script with 10 scenes, converts scripts to audio, creates dynamic images, and stitches them into a video with synchronized subtitles. The application is designed to narrate news in a cool, engaging way targeted at younger audiences, explaining the impact and relevance of the news. It uses external APIs (NewsAPI, OpenAI, Runware) and runs in a Dockerized environment for portability.

## Features
- **News Fetching**: Retrieves top headlines from NewsAPI based on country, category, or query.
- **Script Generation**: Uses OpenAI GPT-4 to create a 2-minute script with 10 scenes, including an opening and a call-to-action to subscribe.
- **Audio Generation**: Converts scripts to audio using OpenAI's TTS (text-to-speech) with the "nova" voice.
- **Image Generation**: Creates vibrant, abstract images for each scene using Runware's image inference API.
- **Video Stitching**: Combines audio, images, and dynamic subtitles into a vertical video (1080x1920 or 1152x2048) using `moviepy` and `Pillow`.
- **Dynamic Subtitles**: Adds word-highlighted subtitles in the third quarter of the screen, styled with Montserrat font for social media appeal.
- **Streaming API**: Provides a Server-Sent Events (SSE) endpoint (`/stream`) to track pipeline progress in real-time.
- **Test Endpoint**: Generates a video from a sample JSON payload for testing (`/test-video`).

## Project Structure
- **`app.py`**: Main FastAPI application defining the `/stream` and `/test-video` endpoints, orchestrating the pipeline (news fetching, script generation, audio, images, video stitching).
- **`video_service.py`**: Service layer for video generation, handling JSON payload parsing, image downloading, and video creation via `VideoGenerator`.
- **`video_generator.py`**: Core video generation logic, creating scenes with images, audio, and dynamic subtitles using `moviepy` and `Pillow`.
- **`video_subtitle_generator.py`**: Alternative subtitle generator using speech recognition for word-level sync (not used in the main pipeline).
- **`payload_parser.py`**: Parses JSON payloads into `Scene` and `Payload` objects for structured data handling.
- **`environment.yml`**: Conda environment configuration with dependencies (Python 3.10, FastAPI, OpenAI, etc.).
- **`Dockerfile`**: Defines the Docker image setup using Miniconda, installing dependencies and running the FastAPI app.
- **`run.sh`**: Script to build and run the Docker container, mapping port 28080 and mounting a data volume.

## Prerequisites
- **Docker**: Required to build and run the application in a containerized environment.
- **API Keys**:
  - **NewsAPI**: For fetching news articles (`NEWS_API_KEY`).
  - **OpenAI**: For script and audio generation (`OPENAI_API_KEY`).
  - **Runware**: For image generation (`RUNWARE_API_KEY`).
- **System Fonts**: Montserrat-Bold.ttf or fallback fonts (e.g., DejaVuSans-Bold, LiberationSans-Bold) for subtitle rendering.
- **Internet Access**: For downloading fonts and accessing external APIs.

## Setup Instructions

1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Set Up Environment Variables**:
   Create a `.env` file in the project root with the following:
   ```env
   NEWS_API_KEY=<your-newsapi-key>
   OPENAI_API_KEY=<your-openai-key>
   RUNWARE_API_KEY=<your-runware-key>
   ```

3. **Ensure Fonts**:
   - The application downloads `Montserrat-Bold.ttf` to `/tmp` (Linux) or `%TEMP%` (Windows). If this fails, manually place the font in the temp directory or install system fonts:
     ```bash
     # On Ubuntu/Debian
     sudo apt-get install fonts-dejavu fonts-liberation
     ```
   - Alternatively, update `video_generator.py` to use a specific font path.

4. **Build and Run with Docker**:
   - Run the provided `run.sh` script to build the Docker image and start the container:
     ```bash
     chmod +x run.sh
     ./run.sh
     ```
   - This maps port `28080` on the host to `28080` in the container and mounts the `./data` directory to `/app/data` for persistent storage.

5. **Manual Docker Commands** (if not using `run.sh`):
   ```bash
   docker build -t short_automation .
   docker run -p 28080:28080 -v $(pwd)/data:/app/data short_automation
   ```

## Usage

### Running the Application
- The FastAPI server runs on `http://localhost:28080`.
- Access the endpoints using a browser, `curl`, or a custom client.

### Endpoints

1. **`/stream` (GET)**:
   - Streams the video generation pipeline as Server-Sent Events (SSE).
   - Query parameters:
     - `country` (default: "us"): Country code for news (e.g., "us", "gb").
     - `category` (default: "business"): News category (e.g., "business", "technology").
     - `query` (optional): Search term for news (e.g., "AI").
   - Example:
     ```bash
     curl http://localhost:28080/stream?country=us&category=technology&query=AI
     ```
   - Response: SSE stream with JSON messages for each task (0 to 5, plus "Completed").
   - Output: Video saved to `data/<request_id>/final_video.mp4`.

2. **`/test-video` (GET)**:
   - Generates a video from a sample JSON payload (`data/f851c750-b4a6-45fa-b23d-5c268e738e95/payload.json`).
   - Returns the video as a downloadable MP4 file.
   - Example:
     ```bash
     curl -o test_video.mp4 http://localhost:28080/test-video
     ```
   - Output: Video saved to `data/test_video.mp4` and returned in the response.

### Pipeline Tasks
The `/stream` endpoint executes the following tasks:
1. **Task 1**: Fetch news from NewsAPI.
2. **Task 2**: Generate a 10-scene script using OpenAI GPT-4.
3. **Task 2a**: Serialize and validate the script JSON.
4. **Task 3**: Convert scripts to audio using OpenAI TTS.
5. **Task 4**: Generate images for each scene using Runware.
6. **Task 5**: Stitch audio, images, and subtitles into a video using `VideoService`.

### Sample JSON Payload
The `payload.json` file (generated in `task5_stitch_video`) has the following structure:
```json
{
  "scenes": "10",
  "1": {
    "scene_id": "<uuid>",
    "script": "Welcome to our daily news blast!",
    "imagePrompt": "Vibrant abstract scene with swirling colors...",
    "audioPath": "data/<request_id>/audio-1.mp3",
    "imageUrl": "https://example.com/image1.jpg"
  },
  ...
  "10": {
    "scene_id": "<uuid>",
    "script": "Subscribe for daily news updates!",
    "imagePrompt": "Dynamic scene with a subscribe button silhouette...",
    "audioPath": "data/<request_id>/audio-10.mp3",
    "imageUrl": "https://example.com/image10.jpg"
  },
  "metadata": {
    "title": "Tech News Update",
    "description": "Latest in AI and tech"
  },
  "request_id": "<uuid>"
}
```

## Dependencies
Defined in `environment.yml`:
- Python 3.10
- FastAPI, Uvicorn, httpx
- OpenAI, newsapi-python, runware
- moviepy (1.0.3), Pillow (9.5.0), numpy
- ffmpeg, imageio-ffmpeg
- python-dotenv, requests

## Docker Setup
- Base Image: `continuumio/miniconda3`
- Environment: Conda `short_automation` with dependencies from `environment.yml`
- Port: 28080
- Volume: `./data` mounted to `/app/data` for persistent storage

## Troubleshooting
- **Font Errors**: If `Montserrat-Bold.ttf` fails to download, ensure internet access or manually place the font in `/tmp`. Install fallback fonts (`fonts-dejavu`, `fonts-liberation`) in the Docker container:
  ```dockerfile
  RUN apt-get update && apt-get install -y fonts-dejavu fonts-liberation
  ```
- **API Key Issues**: Verify `NEWS_API_KEY`, `OPENAI_API_KEY`, and `RUNWARE_API_KEY` in `.env`.
- **Stream Not Closing**: Ensure the client closes the SSE connection after receiving the "Completed" message. Test with a JavaScript SSE client:
  ```javascript
  const source = new EventSource('http://localhost:28080/stream');
  source.onmessage = function(event) {
      console.log(event.data);
      if (event.data === '{}') source.close();
  };
  ```
- **Video Generation Errors**: Check logs in `data/<request_id>` for issues with `VideoService` or `VideoGenerator`. Ensure `ffmpeg` is installed in the container.

## Limitations
- **VideoSubtitleGenerator**: Not integrated into the main pipeline; uses speech recognition, which requires internet access and may be less reliable than `VideoGenerator`’s script-based subtitles.
- **Font Dependency**: Relies on Montserrat or system fonts; fallback to PIL’s default font may result in smaller text.
- **API Quotas**: NewsAPI, OpenAI, and Runware have rate limits; monitor usage to avoid throttling.
- **Docker Volume**: Ensure the `./data` directory is writable on the host.

## Future Improvements
- Integrate `VideoSubtitleGenerator` for more accurate word-level subtitle sync.
- Add support for multiple video resolutions or aspect ratios.
- Implement caching for API responses to reduce costs and latency.
- Enhance error handling with retries for API failures.
- Add a UI for easier interaction with the `/stream` endpoint.

## Contributing
Contributions are welcome! Please submit issues or pull requests to the repository. Focus areas:
- Improving subtitle styling (e.g., animations, color schemes).
- Optimizing video rendering performance.
- Adding support for additional news sources or languages.

## License
This project is licensed under the MIT License. See the `LICENSE` file for details.

## Contact
For questions or support, contact the project maintainers via GitHub Issues.
