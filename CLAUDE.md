# CLAUDE.md - MCP-SSE Project Guide

## Build/Run Commands
- Setup: `uv create` (create virtual env)
- Run server: `uv run weather.py [--host HOST] [--port PORT]`
- Run client: `uv run client.py <SERVER_URL>`
- Test: No specific test commands defined

## Code Style Guidelines
- **Imports**: Group standard library, third-party, and local imports
- **Formatting**: Use consistent 4-space indentation in Python
- **Types**: Use Python type annotations (`from typing import ...`)
- **Naming**: Use `snake_case` for variables/functions, `PascalCase` for classes
- **Error Handling**: Use try/except blocks with specific exceptions
- **Async**: Use asyncio for asynchronous code with proper cleanup
- **Documentation**: Use docstrings for functions/classes
- **Constants**: Define constants at module level in UPPERCASE
- **Environment**: Use dotenv for environment variables

## Best Practices
- Follow MCP protocol specifications when implementing clients/servers
- Handle proper resource cleanup with async context managers
- Implement proper error handling for HTTP requests