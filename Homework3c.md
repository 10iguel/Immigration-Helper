# Homework 3c

## How you completed the required tasks

- I built GitHub bit, a console agent based on the example of the map bot. It connects to GitHub's official remote MCP 
server as a hosted MCP tool in the OpenAI Responses API and authenticates with a fine-grained 
Personal Access Token. I tested it on my own account by asking the agent to list my 30 repositories 
and explored the folders of my Immigration-Helper repo with get_file_contents.

## What additional exploration you did

- I made the agent safe by design. The token only has read permissions, and the X-MCP-Readonly, set to true, header hides every write tool on 
the server side. The X-MCP-Toolsets header loads only the context, repos, issues and pull_requests toolsets instead of 
all the 100 tools, which cuts the input tokens sent on every request. When I asked the bot to create an issue, it made no tool call 
and explained that it only has read access.

## What obstacles you encountered

- The agent wasn't fully reliable even with correct tools. When it refused to create the issue, it misquoted the title I gave it 
("testing from mcp with the testing mcp" instead of "testing mcp"). It also fetched the same folder twice while counting files
and the set-up for the token had to be fixed because I gave the right permissions for some repositories to create issues and
it did not work

## What you learned

- Connecting to a well-known third-party MCP server takes very little code, the server URL, an auth header and a system prompt. Most
of the real engineering is choosing which tools the model can see, scoping credentials, and checking that the model's answers 
actually match the tool results.

## Why this matters in the context of agent engineering

- An agent that has access to real accounts can cause real damage, so permissions should be limited in layers. For example, the credential itself 
(a read-only token scoped to selected repos), the server (read-only mode and limited toolsets), and the prompt. That way, safety doesn't 
depend only on the model choosing to behave.

## Final Project Status

- 
## How many hours you spent on the homework

- 3.0 hours
