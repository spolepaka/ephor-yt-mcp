# YouTube MCP Server

An SSE-based MCP (Model Context Protocol) server that provides YouTube search and video data capabilities.

## Features

This server provides the following tools to AI models via the MCP protocol:

- **search**: Search for YouTube videos with customizable result limits
- **get_video_info**: Get detailed information about a specific YouTube video
- **get_transcript**: Retrieve transcript data from YouTube videos

## Installation

1. Clone this repository
2. Install dependencies with uv:

```bash
uv pip install httpx mcp starlette uvicorn
```

Or alternatively:

```bash
uv pip install -r requirements.txt
```

## Usage

### Start the server

```bash
uv run youtube-mcp.py
```

By default, the server runs on `0.0.0.0:8080`. You can customize the host and port:

```bash
uv run youtube-mcp.py --host localhost --port 8080
```

### Connect with a client

You can connect to the server using an MCP client. Example:

```bash
uv run client.py http://localhost:8080/sse
```

### Available Tools

#### search

Search for YouTube videos.

Parameters:
- `query`: The search query (string)
- `limit`: Maximum number of results to return, between 1-10 (integer, default: 5)

#### get_video_info

Get detailed information about a YouTube video.

Parameters:
- `input`: YouTube video ID or URL (string)

#### get_transcript

Get transcript for a YouTube video.

Parameters:
- `input`: YouTube video ID or URL (string)

## Integration with Cursor

To configure this server as an MCP tool in Cursor:

1. Add the following to your Cursor configuration (`~/.cursor/mcp.json`):

```json
{
  "youtube-mcp": {
    "url": "http://localhost:8080/sse"
  }
}
```

2. Start the YouTube MCP server
3. Use the tools in Cursor by referring to them with the `mcp_youtube_mcp_` prefix

## License

This project is provided as-is with no warranty.
