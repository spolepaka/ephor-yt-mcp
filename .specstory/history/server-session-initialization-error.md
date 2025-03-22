## SpecStory

## Server Session Initialization Error (3/21/2025, 6:13:32 PM)

_**User**_

Why?

---

_**Assistant**_

The error occurs because there's an issue with the initialization options being passed to the ServerSession. The error message shows: `AttributeError: 'dict' object has no attribute 'capabilities'` - the code is trying to access a 'capabilities' attribute on an object that's actually a plain dictionary.

Let me check the relevant code to fix this.

---

_****_

Read file: undefined

---

_****_

Let me look at the handling of initialization options in the ServerSession:

---

_****_

Read file: undefined

---

_****_

I need to look at the initialization options structure:

---

_****_

Read file: undefined

---

_****_

Now I need to check the InitializationOptions class:

---

_****_

Read file: undefined

---

_****_

Now I understand the issue. The error is occurring because we're passing a plain dict (`{}`) as initialization options in `youtube-mcp.py` around line 355, but the `ServerSession` class expects an `InitializationOptions` object with a `capabilities` attribute.

Let's fix this:

---

_****_

```diff
  import sys
  import asyncio
+ from mcp.server.models import InitializationOptions
+ from mcp.types import ServerCapabilities
  
  # Initialize FastMCP server for YouTube tools (SSE)
                  request._send,  # noqa: SLF001
          ) as (read_stream, write_stream):
-             # Use empty initialization options since the server doesn't have the create_initialization_options method
-             init_options = {}
+             # Create proper initialization options with capabilities
+             init_options = InitializationOptions(
+                 server_name="youtube-search",
+                 server_version="1.0.0",
+                 capabilities=ServerCapabilities()
+             )
+             
              await mcp_server.run(
                  read_stream,
```

---

_****_

Great! Now let's run the YouTube MCP server with the fix:

---

_****_



---

_**User**_

What is the error we are getting now and why? Just analyze do not fix yet.

---

_**Assistant**_

The error you're now seeing is a connection timeout error:

```
SSE error: TypeError: fetch failed: Connect Timeout Error (attempted addresses: 216.198.79.65:8080, 64.29.17.65:8080, timeout: 10000ms)
```

Based on this error message:

1. The Cursor IDE's MCP client is attempting to connect to IP addresses 216.198.79.65 and 64.29.17.65 on port 8080, but these connection attempts are timing out after 10 seconds.

2. Despite starting your server on port 3000 with `uv run youtube-mcp.py --port 3000`, the client is still trying to connect to port 8080.

3. Looking at the code, I can see the issue is in the URL paths. In your `create_starlette_app` function, you're setting up routes including `/sse`, but the error message suggests Cursor is trying to connect to a different port (8080) than the one your server is running on (3000).

4. In the server output, you can see the server successfully started on port 3000 and is accepting connections, but the client is trying to connect to a different port/address.

The issue appears to be a mismatch between where your server is running and where Cursor is configured to look for the MCP server.

---

_**User**_

how do we fix the above error?

---

_**Assistant**_



---



---

