from typing import Any, Dict, List, Optional
import json
import re
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server import Server
import uvicorn
import argparse
import signal
import sys

# Initialize FastMCP server for YouTube tools (SSE)
mcp = FastMCP("youtube-search")

# Constants
COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-User': '?1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control': 'max-age=0'
}


def extract_video_id(input_str: str) -> Optional[str]:
    """Extract YouTube video ID from URL or return the ID if already valid."""
    # If input is already a valid video ID (11 characters), return it
    if re.match(r'^[a-zA-Z0-9_-]{11}$', input_str):
        return input_str

    # Handle various YouTube URL formats
    patterns = [
        # Standard watch URL: https://www.youtube.com/watch?v=VIDEO_ID
        r'(?:youtube\.com\/watch\?v=)([^"&?\/\s]{11})',
        # Short URL: https://youtu.be/VIDEO_ID
        r'(?:youtu\.be\/)([^"&?\/\s]{11})',
        # Embed URL: https://www.youtube.com/embed/VIDEO_ID
        r'(?:youtube\.com\/embed\/)([^"&?\/\s]{11})',
        # Short URL with timestamp: https://youtu.be/VIDEO_ID?t=123
        r'(?:youtu\.be\/|youtube\.com\/watch\?v=)([^"&?\/\s]{11})',
        # Mobile URL: https://m.youtube.com/watch?v=VIDEO_ID
        r'(?:m\.youtube\.com\/watch\?v=)([^"&?\/\s]{11})',
        # Music URL: https://music.youtube.com/watch?v=VIDEO_ID
        r'(?:music\.youtube\.com\/watch\?v=)([^"&?\/\s]{11})'
    ]

    for pattern in patterns:
        match = re.search(pattern, input_str)
        if match and match.group(1):
            return match.group(1)

    return None


def extract_initial_data(html: str) -> Optional[Dict]:
    """Extract ytInitialData from YouTube page."""
    try:
        match = re.search(r'var ytInitialData = ({.*?});', html)
        if match and match.group(1):
            return json.loads(match.group(1))
        return None
    except Exception as e:
        print(f"Error parsing initial data: {e}")
        return None


async def extract_transcript(video_id: str) -> Dict[str, Any]:
    """Extract transcript from a YouTube video."""
    try:
        # First get the video page to extract initial data
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://www.youtube.com/watch?v={video_id}",
                headers={**COMMON_HEADERS, 'Referer': 'https://www.youtube.com/results'},
                follow_redirects=True,
                timeout=30.0
            )
        
        response.raise_for_status()
        html = response.text
        
        # Extract the ytInitialPlayerResponse which contains captions data
        player_response_match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', html)
        if not player_response_match:
            raise ValueError('Could not find player response data')

        player_response = json.loads(player_response_match.group(1))
        captions = player_response.get('captions', {}).get('playerCaptionsTracklistRenderer', {}).get('captionTracks', [])
        
        if not captions:
            raise ValueError('No transcript available for this video')

        # Find English captions, or use the first available if no English
        caption_track = next((track for track in captions if track.get('languageCode') == 'en'), captions[0])
        if not caption_track.get('baseUrl'):
            raise ValueError('Could not find caption track URL')

        # Fetch the actual transcript
        async with httpx.AsyncClient() as client:
            transcript_response = await client.get(caption_track['baseUrl'] + '&fmt=json3')
        
        transcript_response.raise_for_status()
        transcript_data = transcript_response.json()
        transcript_events = transcript_data.get('events', [])

        # Process transcript events into a readable format
        processed_transcript = []
        for event in transcript_events:
            if 'segs' not in event:
                continue
                
            start_time = event.get('tStartMs', 0) / 1000  # Convert to seconds
            text = ' '.join(seg.get('utf8', '') for seg in event['segs']).strip()
            if text:
                processed_transcript.append({
                    'time': f"{start_time:.2f}",
                    'text': text
                })

        # Get video info from the player response
        video_info = {
            'title': player_response.get('videoDetails', {}).get('title', ''),
            'channel': {
                'name': player_response.get('videoDetails', {}).get('author', ''),
            },
            'duration': player_response.get('videoDetails', {}).get('lengthSeconds', '')
        }

        return {
            'transcript': processed_transcript,
            'videoInfo': video_info
        }
    except Exception as e:
        print(f"Transcript extraction error: {e}")
        raise


async def perform_youtube_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Perform a YouTube search and return video results."""
    try:
        search_url = f"https://www.youtube.com/results?search_query={query}&sp=CAISAhAB"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                search_url,
                headers={**COMMON_HEADERS, 'Referer': 'https://www.youtube.com/'},
                follow_redirects=True,
                timeout=30.0
            )
        
        response.raise_for_status()
        html = response.text
        initial_data = extract_initial_data(html)

        if not initial_data:
            raise ValueError('Could not extract video data from page')

        results = []
        contents = (
            initial_data.get('contents', {})
            .get('twoColumnSearchResultsRenderer', {})
            .get('primaryContents', {})
            .get('sectionListRenderer', {})
            .get('contents', [{}])[0]
            .get('itemSectionRenderer', {})
            .get('contents', [])
        )

        for item in contents:
            if len(results) >= limit:
                break

            video_renderer = item.get('videoRenderer')
            if not video_renderer:
                continue

            video_id = video_renderer.get('videoId')
            title = video_renderer.get('title', {}).get('runs', [{}])[0].get('text', '')
            
            if not (video_id and title):
                continue
                
            result = {
                'videoId': video_id,
                'title': title,
                'url': f"https://youtube.com/watch?v={video_id}",
                'thumbnailUrl': video_renderer.get('thumbnail', {}).get('thumbnails', [{}])[0].get('url', ''),
                'description': video_renderer.get('descriptionSnippet', {}).get('runs', [{}])[0].get('text', ''),
                'channel': {
                    'name': video_renderer.get('ownerText', {}).get('runs', [{}])[0].get('text', ''),
                    'url': video_renderer.get('ownerText', {}).get('runs', [{}])[0].get('navigationEndpoint', {})
                        .get('commandMetadata', {}).get('webCommandMetadata', {}).get('url', '')
                },
                'viewCount': video_renderer.get('viewCountText', {}).get('simpleText', ''),
                'publishedTime': video_renderer.get('publishedTimeText', {}).get('simpleText', '')
            }
            
            results.append(result)

        return results
    except Exception as e:
        print(f"Search error: {e}")
        raise ValueError(f"Failed to perform YouTube search: {str(e)}")


@mcp.tool()
async def search(query: str, limit: int = 5) -> str:
    """Search for YouTube videos.
    
    Args:
        query: The search query
        limit: Maximum number of results to return (1-10)
    """
    if limit < 1:
        limit = 1
    elif limit > 10:
        limit = 10
        
    try:
        results = await perform_youtube_search(query, limit)
        if not results:
            return "No results found for the given query."
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error performing search: {str(e)}"


@mcp.tool()
async def get_video_info(input: str) -> str:
    """Get detailed information about a YouTube video.
    
    Args:
        input: YouTube video ID or URL
    """
    try:
        video_id = extract_video_id(input)
        
        if not video_id:
            return f"Error: Invalid YouTube video ID or URL: {input}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://www.youtube.com/watch?v={video_id}",
                headers={**COMMON_HEADERS, 'Referer': 'https://www.youtube.com/results'},
                follow_redirects=True,
                timeout=30.0
            )
        
        response.raise_for_status()
        html = response.text
        initial_data = extract_initial_data(html)

        if not initial_data:
            return "Could not extract video data from page"

        video_data = (
            initial_data.get('contents', {})
            .get('twoColumnWatchNextResults', {})
            .get('results', {})
            .get('results', {})
            .get('contents', [{}])[0]
            .get('videoPrimaryInfoRenderer', {})
        )
        
        channel_data = (
            initial_data.get('contents', {})
            .get('twoColumnWatchNextResults', {})
            .get('results', {})
            .get('results', {})
            .get('contents', [{}])[1]
            .get('videoSecondaryInfoRenderer', {})
        )

        if not video_data:
            return "Could not find video data"

        # Extract description text from runs
        description = ""
        if channel_data and 'description' in channel_data and 'runs' in channel_data['description']:
            description = ''.join(run.get('text', '') for run in channel_data['description']['runs'])

        result = {
            'videoId': video_id,
            'title': video_data.get('title', {}).get('runs', [{}])[0].get('text', ''),
            'description': description,
            'viewCount': video_data.get('viewCount', {}).get('videoViewCountRenderer', {}).get('viewCount', {}).get('simpleText', ''),
            'publishDate': video_data.get('dateText', {}).get('simpleText', ''),
            'channel': {
                'name': channel_data.get('owner', {}).get('videoOwnerRenderer', {}).get('title', {}).get('runs', [{}])[0].get('text', ''),
                'url': channel_data.get('owner', {}).get('videoOwnerRenderer', {}).get('navigationEndpoint', {})
                    .get('commandMetadata', {}).get('webCommandMetadata', {}).get('url', '')
            },
            'thumbnailUrl': f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            'url': f"https://youtube.com/watch?v={video_id}"
        }

        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error fetching video info: {str(e)}"


@mcp.tool()
async def get_transcript(input: str) -> str:
    """Get transcript for a YouTube video.
    
    Args:
        input: YouTube video ID or URL
    """
    try:
        video_id = extract_video_id(input)
        
        if not video_id:
            return f"Error: Invalid YouTube video ID or URL: {input}"

        transcript_data = await extract_transcript(video_id)
        
        result = {
            'videoId': video_id,
            'videoInfo': transcript_data['videoInfo'],
            'transcript': transcript_data['transcript']
        }

        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error fetching transcript: {str(e)}"


def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can serve the provided mcp server with SSE."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send,  # noqa: SLF001
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )
            
    # Create a router to handle root path
    async def root_handler(request: Request):
        from starlette.responses import HTMLResponse
        return HTMLResponse("""
        <html>
            <head>
                <title>YouTube MCP Server</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
                    code { background: #f4f4f4; padding: 2px 4px; border-radius: 4px; }
                </style>
            </head>
            <body>
                <h1>YouTube MCP Server</h1>
                <p>Server is running successfully.</p>
                <p>To connect, use: <code>uv run client.py http://localhost:8080/sse</code></p>
                <p>Available tools:</p>
                <ul>
                    <li><code>search</code> - Search for YouTube videos</li>
                    <li><code>get_video_info</code> - Get detailed video information</li>
                    <li><code>get_transcript</code> - Get video transcript data</li>
                </ul>
            </body>
        </html>
        """)

    return Starlette(
        debug=debug,
        routes=[
            Route("/", endpoint=root_handler),
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )


# Define signal handler for graceful shutdown
def signal_handler(sig, frame):
    print("\nShutting down server gracefully...")
    sys.exit(0)


if __name__ == "__main__":
    mcp_server = mcp._mcp_server  # noqa: WPS437
    
    parser = argparse.ArgumentParser(description='Run YouTube MCP SSE-based server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on')
    args = parser.parse_args()

    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    print("YouTube Search MCP Server starting...")
    print(f"Server running at http://{args.host}:{args.port}")
    print("Use Ctrl+C to stop the server")
    print("Client command: uv run client.py http://localhost:8080/sse")
    print("Questions or feedback? Connect with @spolepaka/youtube-mcp | X: @skpolepaka")
    
    # Bind SSE request handling to MCP server
    starlette_app = create_starlette_app(mcp_server, debug=True)
    
    # Start server with custom signal handling
    uvicorn.run(starlette_app, host=args.host, port=args.port, lifespan="on")