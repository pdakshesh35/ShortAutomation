# Architecture Diagram

```mermaid
flowchart TD
    client[Client or Automation Trigger] --> api[FastAPI App (app.py)]
    api --> pipeline{Pipeline Tasks}
    pipeline --> fetch[Fetch News (NewsNiche.fetch_content)]
    pipeline --> script[Generate Script (OpenAI)]
    pipeline --> serialize[Serialize & Validate Script]
    pipeline --> tts[Convert Script to Audio (OpenAI TTS)]
    pipeline --> images[Generate Images (Runware)]
    pipeline --> video[Stitch Video (VideoService)]
    video --> generator[VideoGenerator]
    generator --> output[Final MP4 Video]
```

The FastAPI application streams each task as it completes via Server-Sent Events. `VideoService`
uses `VideoGenerator` to combine downloaded images, audio, and dynamic subtitles into the final
vertical video.
