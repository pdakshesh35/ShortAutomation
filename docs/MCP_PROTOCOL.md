# Model Context Protocol (MCP)

The Model Context Protocol exposes each stage of the video generation pipeline as a callable `mcp.tool`. These tools can be invoked programmatically, allowing an LLM to control the pipeline step by step.

## Available Tools

| Tool Name | Task ID | Description |
|-----------|---------|-------------|
| `init_request` | `0` | Create a new `MCPContext` and return the request identifier. |
| `fetch_content` | `1` | Fetch news content for the given niche. |
| `generate_script` | `2` | Use OpenAI to create a multi-scene script. |
| `serialize_script` | `2a` | Validate the script JSON and attach scene IDs. |
| `convert_scripts_to_audio` | `3` | Generate audio files for each scene using TTS. |
| `generate_scene_images` | `4` | Create images for each scene via Runware. |
| `stitch_video` | `5` | Combine images, audio and subtitles into the final video. |

Each tool accepts an `MCPContext` instance (created by `init_request`) and additional parameters needed for that step. Tools return a list of JSON status messages identical to those streamed by the REST `/stream` endpoint.

## Example Usage

```python
from mcp.context import MCPContext
from mcp import tools

# Step 0: initialise
ctx = await tools.init_request("news")

# Step 1: fetch article
messages = await tools.fetch_content(ctx, country="us", category="business", query="AI")
for m in messages:
    print(m)

# continue with other tools...
```

The MCP tools mirror the pipeline steps described in the [README](../README.md). LLM agents can call these tools sequentially to generate a short-form news video.
