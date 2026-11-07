# Homework 3b

## How you completed the required tasks

- I built a small tool-calling agent in Python using the OpenAI API and ran it inside a Docker container as my sandbox.
The agent has two tools, `run_shell` and `write_file`, and both only work inside the container's `/workspace` folder.
I chat with it in the terminal, and I watched it write and run a Python script in the sandbox. The container
runs as a non-root user, with a read-only filesystem, all Linux capabilities dropped, and memory, CPU and process limits.
It is deleted after every run, so each session starts clean.

## What additional exploration you did

- I tried a browser chat UI with Gradio, but dropped it because it added about 40 extra dependencies and more attack
surface for something the terminal already did. I also compared other ways to sandbox an agent like hardened container
runtimes using gVisor, Kata, Firecracker microVMs, full VMs, and OS-level tools
like bubblewrap.

## What obstacles you encountered

- My first image had critical vulnerabilities, from an outdated base image and old package versions. Upgrading them
broke the build, because I had locked the dependencies for Python 3.13 while the Dockerfile still used Python 3.12 . Also
found that the agent could read my OPENAI_API_KEY by running echo $OPENAI_API_KEY or cat /proc/1/environ, 
so I removed secrets from the shell tool's environment and made the agent process hide its own memory from the commands it runs.

## What you learned

- I learned that a sandbox is more than putting the agent in a container. The container stops the agent from touching
my computer, but secrets inside the container, outdated dependencies, and missing resource limits can still be abused.
I also learned that containers share the host's kernel. Keeping the tools behind a `Tool` abstraction 
would also make it easy to swap Docker for another sandbox later.

## Why this matters in the context of agent engineering

- An agent runs code and commands that a model generated, and a prompt injection in a file or web page could turn
that into harmful actions, like deleting files or leaking API keys. A sandbox limits the damage when the model gets
something wrong or is manipulated, so the agent can be given real tools without trusting it blindly. This matters
for my USCIS Form Helper, which will handle sensitive personal documents, those must stay isolated and must never
leak through a tool call.

## Final Project Status

- 

## How many hours you spent on the homework

- 3.0 hours
