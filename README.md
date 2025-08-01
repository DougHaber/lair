<div align="center">

# Lair

CLI Tools for Working With Generative AI

[Installation](#installation) |
[Configuration](#configuration) |
[Features](#features) |
[Changelog](CHANGELOG.md)

Modules: [Chat](#chat---command-line-chat-interface) |
[Comfy](#comfy) |
[Util](#util)

</div>

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Overview](#overview)
- [Features](#features)
- [Future](#future)
- [Installation](#installation)
- [Configuration](#configuration)
- [Lair Core](#lair-core)
  - [Common Command Line Options](#common-command-line-options)
  - [Prompt Templates](#prompt-templates)
- [Chat - Command Line Chat Interface](#chat---command-line-chat-interface)
  - [Commands](#commands)
  - [Shortcut Keys](#shortcut-keys)
  - [Markdown Rendering](#markdown-rendering)
  - [Session Management](#session-management)
    - [Session Database](#session-database)
    - [Session Management Commands and Shortcuts](#session-management-commands-and-shortcuts)
    - [Session Titles](#session-titles)
  - [Reasoning Models](#reasoning-models)
  - [Chat Examples](#chat-examples)
    - [Attaching Files](#attaching-files)
    - [Tools](#tools)
      - [Python Tool](#python-tool)
      - [Search Tool](#search-tool)
      - [File Tool](#file-tool)
      - [Tmux Tool](#tmux-tool)
      - [MCP Tool](#mcp-tool)
    - [One-off Chat](#one-off-chat)
    - [Extracting Embedded Responses](#extracting-embedded-responses)
    - [Modifying Chat History](#modifying-chat-history)
  - [Model Settings](#model-settings)
  - [File Based Session Management](#file-based-session-management)
  - [Calling Comfy Workflows](#calling-comfy-workflows)
- [Comfy](#comfy)
  - [Workflows and Dependencies](#workflows-and-dependencies)
  - [Comfy Usage & Examples](#comfy-usage--examples)
    - [image - Image Generation](#image---image-generation)
    - [ltxv-i2v - LTX Video Image to Video](#ltxv-i2v---ltx-video-image-to-video)
    - [ltxv-prompt - LTX Video Prompt Generation via Florence2](#ltxv-prompt---ltx-video-prompt-generation-via-florence2)
    - [hunyuan-video-t2v - Hunyuan Video Text to Video](#hunyuan-video-t2v---hunyuan-video-text-to-video)
    - [upscale - Enlarge Images and Enhance Quality](#upscale---enlarge-images-and-enhance-quality)
    - [outpaint - Extend Images](#outpaint---extend-images)
- [Util](#util)
  - [Util Examples](#util-examples)
    - [Generating Content](#generating-content)
    - [Providing Input Content](#providing-input-content)
    - [Attaching Files](#attaching-files-1)
    - [Using Tools](#using-tools)
    - [Using Sessions](#using-sessions)

<!-- markdown-toc end -->


## Overview

Lair is a command-line tool for working with generative AI. It provides a feature-rich chat interface and utilities for interacting with both language models (LLMs) and diffusion models. Lair aims to make generative AI accessible from the command line and easy to use with shell scripting. It's chat interface provides many keyboard shorcuts and tools for helping experiment with prompt engineering.

The open-source version of Lair is a partial rewrite of the original closed-source project. The original included additional features such as an agent framework, evolutionary programming tools for LLMs, and a utility for generating non-temporal videos from image diffusion models. While some traces of these features may still exist in the code, many are not currently included in the open-source release. Future updates may reintroduce select functionality from the original version.

**Introduction Video**

[![Lair CLI Introduction](images/lair-into-youtube.jpg)](https://www.youtube.com/watch?v=mWQFoS2Xge8)


## Features

* **chat**: Command line chat interface
  * Rich interface w/ auto-complete, commands, shortcuts, etc
  * Session management, fast session switching, and persistent sessions
  * Support for image, PDF, and text attachments
  * Markdown rendering & syntax highlighting
  * Customizable styling for reasoning model output
  * Support for extracting content from responses such as code block sections

* **comfy**: Run workflows on ComfyUI
  * Image diffusion, LTX Video, Hunyuan Video, and upscaling support
  * Simple interface for command line usage and scripting

* **util**: Unix-style utility for scripting or one-off LLM usage
  * Simple I/O for sending content via file or pipes to LLMs
  * Support for image, PDF, and text attachments

* Tools Support
  * Works in the chat interface and the util command
  * File Tool: Read and write files in a local path (**Experimental**)
  * Python Tool: Run python code inside of a container
  * Search Tool: Search the web or news with DuckDuckGo
  * Tmux Tool: Interact with terminals in a Tmux sesion (**Experimental**)
  * MCP Tool: Load remote tools from MCP providers

## Future

Lair is a hobby project with no official roadmap or guarantee that anything will be addressed. That said, a [GitHub project exists](https://github.com/users/DougHaber/projects/1) where possible improvements are listed and tracked. GitHub Issues can be created to request new features or report bugs.

## Installation

Lair is installed as a Python command and requires Python 3.10 or later. Any Python package management tool can be used to install Lair, such as `pip`, `pipx`, or `uv`. For most users, `pipx` or `uv` are likely the best options.

```sh
pipx install git+https://github.com/DougHaber/lair.git@0.8.1
```

Replace `0.8.1` with the latest version. The `master` branch contains the latest unreleased version, which may be unstable. Official releases are tagged using semantic versioning.

## Configuration

In Lair, configuration is a set of namespaced key-value pairs. All pairs can be found [here](lair/files/settings.yaml). Types are enforced, and attempting to set a key to a value of a different type will result in an error.

When Lair is first run, it creates `~/.lair/config.yaml`. Within this file, modes can be defined to customize settings. A mode is a named collection of settings, allowing users to quickly switch between different configurations. The top-level `default_mode` key specifies the mode to use if none is specified.

YAML anchors and aliasing can be used to make modes inherit from each other. An experimental feature also allows a key `_inherit` to contain a list of other modes to inherit from. The modes to inherit from must be defined above the point they are referenced. While this feature is available, it should be considered experimental, and its behavior might change in the future.

Modes with names beginning with an underscore are considered hidden and not displayed by the `/mode` command. This is helpful when making modes that are intended to be used with `_inherit`, but not otherwise used directly.

In the chat interface, use the `/set` command to modify settings for an active session. Running `/set` without arguments shows all settings, highlighting those that differ from the defaults. To change a setting, use `/set {key} {value}`. The `/list-settings` command allows searching with regular expressions, showing only differences, or comparing the current mode against a different baseline mode. Use `/list-settings --help` to see all options.

In the current release, the only supported `session.type` is `openai_chat`, which uses OpenAI's API or other APIs that provide compatibility, such as Ollama. Lair originally used LangChain and supported various other options, but these have been removed to simplify the code.

To use Lair with OpenAI, set the environment variable `OPENAI_API_KEY` with your key. The default environment variable to use can be modified with `openai.api_key_environment_variable`.

To use Lair with other OpenAI-compatible APIs, such as Ollama, set the configuration variable `openai.api_base`. For example, to use an Ollama endpoint `openai.api_base: http://localhost:11434/v1`.


## Lair Core

### Common Command Line Options

When running Lair, the following flags can be used at the top level. They must be provided before the sub-command is specified.

```
  -h, --help               show this help message and exit
  --debug, -d              Enable debugging output
  --disable-color, -c      Do not use color escape sequences
  --force-color, -C        Use color escape sequences, even in pipes
  -M MODE, --mode MODE     Name of the predefined mode to use
  -m MODEL, --model MODEL  Name of the model to use
  -s SET, --set SET        Set a configuration value (-s key=value)
  --version                Display the current version and exit
```

The `--mode` / `-M` flag allows setting the mode as well as any associated configuration at startup.

Individual settings may be overridden with the `--set` / `-s` flag. For example `lair -s 'style.error=bold red' -s ui.multline_input=true chat`.

The `--model` / `-m` flag is a shorthand for setting `model.name`.

### Prompt Templates

The system prompt is configured via `session.system_prompt_template`. This allows for defining different modes with custom prompts in `~/.lair/config.yaml` or modifying the prompt dynamically using the `/set` command in the chat interface. When using the `util` sub-command, the prompt is generated based on `util.system_prompt_template`.

Prompts use [Jinja templates](https://jinja.palletsprojects.com/en/stable/templates/), providing a full-featured templating system for customization.

The following variables are automatically available:
- `date`: The current date in UTC, formatted as `%Y-%m-%d UTC`.
- `datetime`: The current date and time in UTC, formatted as `%Y-%m-%d %H:%M:%S UTC`.

**Note:** Using `datetime` or any dynamic prompt behavior can disrupt caching, potentially slowing down future requests. While this may not be an issue for one-time requests, maintaining a stable system prompt is recommended for chat sessions.

Additionally, a `get_config()` function is available, allowing retrieval of configuration values. This can be useful for dynamically adjusting instructions based on the settings. For example, the following YAML configuration modifies the system prompt when tools are enabled:

```yaml
session.system_prompt_template: |-
  You are a friendly assistant.
  TODAYS DATE: {{ date }}
  {%- if get_config('tools.enabled') -%}
  - When using tools:
    - If the search or news tool returns irrelevant results, do not mention them.
    - Do not ask whether to call a tool—just execute it.
  {%- endif -%}
```

The `/last-prompt` command in the chat interface displays the full last prompt, including rendered system messages, which can be useful for debugging prompt templates.

## Chat - Command Line Chat Interface

The `chat` command provides a rich command-line interface for interacting with large language models, as well as some experimental support for diffusion models.

Much of the interface is customizable through overriding `chat.*` & `style.*` settings. See [here](lair/files/settings.yaml) for a full reference for those settings.

The bottom-toolbar by default shows flags like `[lMvW]`. Flags that are enabled show with capital letters and brighter colors. The current flags are:

| Flag | Meaning            | Default Shortcut Key |
|------|--------------------|----------------------|
| L    | Multi-line input   | ESC-L                |
| M    | Markdown rendering | ESC-M                |
| T    | Tools              | ESC-T                |
| V    | Verbose Output     | ESC-V                |
| W    | Word-wrapping      | ESC-W                |

When Verbose output is enabled tool calls and responses are displayed.

The prompt and toolbar can be customized via `chat.*` settings.

### Commands

| Command          | Description                                                                                                             |
|------------------|-------------------------------------------------------------------------------------------------------------------------|
| /clear           | Clear the conversation history                                                                                          |
| /comfy           | Call ComfyUI workflows                                                                                                  |
| /debug           | Toggle debugging                                                                                                        |
| /extract         | Display or save an embedded response  (usage: `/extract [position?] [filename?]`)                                       |
| /help            | Show available commands and shortcuts                                                                                   |
| /history         | Show current conversation                                                                                               |
| /history-edit    | Modify the history JSONL in an external editor                                                                          |
| /history-slice   | Modify the history with a Python style slice string  (usage: `/history-slice [slice]`, Slice format: `start:stop:step`) |
| /last-prompt     | Display the most recently used prompt                                                                                   |
| /last-response   | Display or save the most recently seen response  (usage: `/last-response [filename?]`)                                  |
| /list-models     | Display a list of available models for the current session                                                              |
| /list-settings   | Show and search settings  (for usage, run `/list-settings --help`)                                                      |
| /list-tools      | Show tools and their status                                                                                             |
| /list-mcp-tools  | Show tools discovered via MCP manifests                                                             |
| /load            | Load a session from a file  (usage: `/load [filename?]`, default filename is `chat_session.json`)                       |
| /messages        | Display or save the JSON message history as JSONL (usage: `/messages [filename?]`)                                      |
| /mode            | Show or select a mode  (usage: `/mode [name?]`)                                                                         |
| /model           | Show or set a model  (usage: `/model [name?]`)                                                                          |
| /prompt          | Show or set the system prompt  (usage: `/prompt [prompt?]`)                                                             |
| /reload-settings | Reload settings from disk  (resets everything, except current mode)                                                     |
| /save            | Save the current session to a file  (usage: `/save [filename?]`, default filename is `chat_session.json`)               |
| /session         | List or switch sessions  (usage: `/session [session_id\|alias?]`)                                                       |
| /session-alias   | Set or remove a session alias  (usage: `/session-alias [session_id\|alias] [new_alias?]`)                               |
| /session-delete  | Delete session(s)  (usage: `/session-delete [session_id\|alias\|all]...`)                                               |
| /session-new     | Create a new session                                                                                                    |
| /session-title   | Set or remove a session title  (usage: `/session-title [session_id\|alias] [new_title?]`)                               |
| /set             | Show configuration or set a configuration value for the current mode  (`usage: /set ([key] [value?]`)                   |

### Shortcut Keys

Lair's chat interface offers numerous keyboard shortcuts to enhance usability. Using `/help` or pressing `C-x ?` displays a list of all available shortcuts along with their current bindings.

For those unfamiliar, `C-x ?` means pressing the `Control` key and the `x` key simultaneously, releasing both, and then pressing the `?` key. In contrast, shortcuts like `C-x C-x` indicate that the `Control` key should remain held down while pressing the second key.

In addition to standard GNU Readline-style key combinations, the following shortcuts are provided with these default bindings:

| Shortcut Key | Action                                           |
|--------------|--------------------------------------------------|
| C-x ?        | Show keys and shortcuts                          |
| C-x C-a      | Set an alias for the current session             |
| C-x C-h      | Show the full chat history                       |
| C-x C-t      | set a title for the current session              |
| C-x C-x      | Fast switch to a different session               |
| C-x c        | Clear the current session's history              |
| C-x h        | Show the last two messages from the chat history |
| C-x m        | Show all available models                        |
| C-x n        | Create a new session                             |
| C-x p        | Cycle to the previous session                    |
| C-x s        | Display all sessions                             |
| C-x space    | Cycle to the next session                        |
| C-x t        | Show all available tools                         |
| ESC-b        | Toggle bottom toolbar                            |
| ESC-d        | Toggle debugging output                          |
| ESC-l        | Toggle multi-line input                          |
| ESC-m        | Toggle markdown rendering                        |
| ESC-t        | Toggle tools                                     |
| ESC-v        | Toggle verbose output (tool calls)               |
| ESC-w        | Toggle word wrapping                             |
| F1 - F12     | Switch to session 1-12                           |

Keyboard shortcuts can be modified through `chat.keys.*`.

### Markdown Rendering

By default, responses from LLMs are rendered as Markdown. The Markdown rendering includes features such as tables and code blocks with syntax highlighting.

For most general chat usage, Markdown rendering is beneficial, but it does have some downsides. When rendering as Markdown, some content may be lost. For example, `<tags>` will not render, and some strings may be encoded. For instance, a response of `&lt;` will display as `<`. However, responses within code blocks are always rendered literally.

The `style.render_markdown` setting can be used to toggle this behavior on or off, or configure it differently for specific modes. In the chat interface, the `ESC-M` key combination can also be used to quickly toggle Markdown rendering.

The `/last-response` and `/history` commands respect the current Markdown rendering settings. For example, if a response is rendered in one style and another style is preferred, pressing `ESC-M` will toggle the Markdown rendering. The `/last-response` command can then be used to redisplay the message with the updated rendering.

For instance, with Markdown rendering enabled, the literal `&lt;` is HTML encoded as `<`:

```
crocodile> Print respond with the exact message: &lt;
<
```

Pressing `ESC-M` and trying again shows the literal response without Markdown rendering:

```
crocodile> /last-response
&lt;
```

### Session Management

A **session** in Lair represents the current chat history, configuration, and other active state.

Lair provides built-in support for session management, with sessions stored in a database. Additionally, sessions can be serialized to JSON files using the `/save` and `/load` commands. For details on file-based session management, see [File-Based Session Management](#file-based-session-management).

Database-based session management is a newer feature and may evolve over time.

Sessions are identified by either an **ID** (an integer) or an **alias** (a string). However, aliases cannot be purely numeric to avoid conflicts with session IDs.

When Lair starts, any sessions without messages are automatically removed from the database.

By default, a new session is created on startup unless a session is specified via the `--session` / `-s` flag. This flag accepts either a session ID or alias and switches to that session. If the `--allow-create-session` / `-S` flag is also provided, Lair will create the session if it does not exist and assign it the specified alias.

#### Session Database

Sessions in Lair are stored in an LMDB (Lightning Memory-Mapped Database) located at `~/.lair/sessions` by default. The database size is controlled by the `database.sessions.size` setting, which defaults to 512MB.

If there are many sessions or large attachments, this limit may be reached. When modifying the size limit, Lair will resize the database on startup. However, if other processes are using the database during a resize, they may end up working with an independent version of the database, potentially leading to data loss. To prevent this, it is recommended to exit all Lair processes before resizing.

To delete all sessions quickly, the LMDB directory (with a default of `~/.lair/sessions`) can be safely removed. Lair will automatically recreate it upon the next startup.

#### Session Management Commands and Shortcuts

Lair offers various commands and keyboard shortcuts for managing sessions. These can be customized via the `chat.keys.*` settings.

- **Listing Sessions**
  Running `/session` without arguments displays all available sessions. This can also be accessed with `C-x s`.

- **Switching Sessions**
  - Use `/session [id|alias]` to switch sessions.
  - The `C-x C-x` shortcut opens a fast switch prompt. At the prompt, entering a session ID or alias switches to that session. Pressing Enter without input switches to the last used session.
  - The **F1–F12** keys allow fast switching between sessions **1–12**.

- **Creating a New Session**
  - Use `/session-new` or `C-x n` to create a new session.

- **Deleting Sessions**
  - Use `/session-delete [id|alias|all]` to delete one or more sessions.
  - Examples:
	- `/session-delete 1 2 3` deletes sessions **1, 2, and 3**.
    - `/session-delete all` removes all sessions including the current one.

- **Setting Session Aliases**
  - Use `/session-alias [id|alias] [new_alias]` to assign an alias.
  - The alias for the current session can be set with `C-x C-a`.

- **Setting Session Titles**
  - Use `/session-title [id|alias] [new_alias]` to assign an title.
  - The alias for the current session can be set with `C-x C-t`.

For a full list of commands and shortcuts, use `/help` or `C-x ?`.

#### Session Titles

Sessions can have **titles** to help identify conversations. Titles may be generated automatically using a truncated version of the first message and response.

Automatic title generation is configurable via `session.auto_generated_titles.*`, allowing customization the model to use, temperature, and prompt template, as well as toggling the feature on or off.

Although different models can be used, they must be accessed through the same provider. For example, if an Ollama endpoint is used, an alternative model name can be specified, but it must be available via the same endpoint.

To set a session title:
- Use `/session-title [id|alias] [new_title]`
- For the current session, use `C-x C-t`.

### Reasoning Models

Reasoning models include "thoughts" in their output. These thoughts may be enclosed in XML-style tags such as `<thought>`, `<think>`, or `<thinking>`. Lair provides customization options to control the appearance and behavior of these tagged responses.

* `style.thoughts.enabled`: Enables or disables fancy rendering of thoughts. When `false`, thoughts are displayed as regular message text. (default: `true`)
* `style.thoughts.hide_tags`: Hides the thought tags themselves while displaying the inner content. (default: `true`)
* `style.thoughts.hide_thoughts`: Hides all text enclosed within thought tags, displaying only the remaining output. (default: `false`)
* `style.llm_output_thought`: Specifies the style for rendering thoughts (e.g., color or formatting). (default: `dim blue`)

![Reasoning Example](docs/images/reasoning.jpg "Reasoning example")

### Chat Examples

#### Attaching Files

Files can be attached by enclosing file names within double angle brackets, such as `<<foo.png>>`. Globbing (wildcards and shell-style sets and pattern matching) and `~` for the home directory are also supported (e.g., `<<~/images/*.png>>`).

Supported file types:

| Type       | Extensions                     | Notes                       |
|------------|--------------------------------|-----------------------------|
| Image      | .gif, .jpeg, .jpg, .png, .webp | Requires a vision model     |
| PDF        | .pdf                           | Converts to text, no images |
| Text Files | * (must not contain binary)    |                             |

Images only work with models that support visual inputs. Providing images to other models might have unpredictable behavior. Some models only can handle a single image per request.

PDFs are converted to text. Some formatting may be lost, and no images are provided to the model.

Support for attaching files can be disabled via `chat.attachments_enabled`. When disabled, the syntax is ignored, and the message is sent to the API as-is. This can be configured or toggled in the chat interface using a command such as: `/set chat.attachments_enabled false`.

The double bracket syntax is customizable via `chat.attachment_syntax_regex`. The [settings.yaml](lair/files/settings.yaml) file contains notes on how to safely modify this setting.

In the following example, an image of two alpacas at a birthday party is provided:

```
crocodile> In just a few words, describe what these alpacas are up to. <<~/alpaca.png>>
Alpaca birthday party with cupcakes.
```

The string `<<~/alpaca.png>>` is automatically removed from the message, so its position within the message does not affect processing.

Text files and PDFs can be included the same way:

```
crocodile> Write a limerick about each of the provided short stories. It must be in proper limerick style and format. <<~/books/*.txt>>
Cool Air by H.P. Lovecraft: There once was a scientist so fine, Investigated strange colds in his time. He sought answers with care, In air that chilled with despair, And found horrors that blurred his mind.

The Eyes Have It by Philip K. Dick: In cities they hid their faces so bright, Yet their eyes betrayed their true sight. A subtle, sly guise, That pierced mortal eyes, Exposing souls in the dark of night.
```

Here is an example using a PDF:

```
crocodile> Using the provided 10-Q for Tesla, please write a summary in the form of a haiku. Respond with only a nicely formatted haiku following strict haiku rules and style. <<tsla-20240930-10-q.pdf>>
Electric dreams ahead
Production ramps, profits rise
Autonomous roads
```

With text and PDF files, the LLM must support large context windows. For users working with Ollama, the default is set low to 2048 tokens, and anything beyond that is truncated causing bad responses. To fix this, adjust the `num_ctx` parameter within Ollama.

By default, filenames are not provided to the LLM, but this behavior can be changed via `misc.provide_attachment_filenames`.

```
# Enable providing filenames
crocodile> /set misc.provide_attachment_filenames true

# Include all files matching ~/test/*.png
crocodile> Provide an accurate one-liner description for each of the provided images. Max 60 characters. Output format: {filename}: {description} <<~/test/*.png>>
Let's take a look at the images. Here are the descriptions:

burrito.png: A colorful, cartoon-style burrito with cheese and vegetables.
comic.png: A cartoon character with a speech bubble saying "Boom!" in yellow text over a blue background.
electron_microscopy.png: An abstract image of a cell membrane with molecules and membranes visible under an electron microscope.
fantasy_art.png: A fantastical drawing of a dragon breathing fire, surrounded by clouds and lightning bolts.
fractal_thanksgiving.png: An artwork of a turkey's feathers made from mathematical fractals for a Thanksgiving celebration.
stained_glass.png: A geometric stained glass window with shapes in red, blue, green, and yellow that resembles stained leadlight art.
```

These descriptions are suboptimal. This example used `llama3.2-vision:11b`, which tends to struggle with multiple images. Providing the filenames also influenced the responses. For this specific request, it would be better to process one file per request and exclude filenames. See the "Attaching Files" section of the "Util" examples below for a different approach.

Assuming the model's context window is large enough, many files can easily be attached. For example, to provide all Python files within the lair repository, something like `<<~/src/lair/lair/**/*.py>>` can be used. The `misc.provide_attachment_filenames` setting should be set to `true` for tasks like this, since the filenames provide context hints and help with communicating back about the structure.

```
openai> Write some notes to help someone new to the provided code base quickly understand the structure. No
recommendations. Just documentation. <<~/src/lair/lair/**/*.py>>

Here's a summary of the code base to help you understand the structure and components:

                                                               Overview

This code base is a chat interface framework built around the concept of a "lair" structure, which is capable of
handling different commands and interacting with language models, particularly OpenAI models.

                                                            Main Components

  1 Chat Interface (ChatInterface):
     • Provides the command line interface (CLI) for interacting with OpenAI models.
     • Uses prompt_toolkit for managing prompt sessions and command completions.
     • Manages command execution and handles user input.
  2 Commands and Completers (ChatInterfaceCommands, ChatInterfaceCompleter):
     • ChatInterfaceCommands manages a set of commands that can be used within the chat interface, such as
	   clearing history or setting configurations.
     • ChatInterfaceCompleter handles tab-completion for known commands and arguments in the chat interface.
  3 Sessions (BaseChatSession, OpenAIChatSession):
     • BaseChatSession is an abstract base class that defines the structure for chat sessions, including
	   history management and model invocation.
     • OpenAIChatSession is a concrete implementation for interacting with OpenAI's API, handling API client
	   creation, and invoking models either directly or through a tool interface.
   ...
```

The response above is truncated, as it continues with additional details across multiple sections.

Attaching files in this manner allows for more than just documentation generation. It can also be used for tasks such as answering specific questions about the codebase, refactoring suggestions, or deeper analysis. Since the attached files remain in the chat history, follow-up questions and iterative requests can be made without reattaching the files.

#### Tools

Tools allow the AI to perform actions beyond generating responses. By utilizing tools, the AI can perform actions such as executing computations and searching news sources, and incorporate the retrieved data into more informed responses.

Since tools enable the AI to take actions that may have unintended consequences, they are disabled by default. To enable them, set `tools.enabled` to `true`.

Each tool has its own configuration namespace and an individual `enabled` flag, which must also be set to `true` in addition to `tools.enabled`.

Tools are only compatible with models that support them. Attempting to use tools with unsupported models may result in errors or unpredictable behavior.

The chat CLI provides the `/list-tools` command to display all available tools and their current status.
Use `/list-mcp-tools` to see only tools loaded from MCP provider manifests.

Tools can be quickly toggled on or off using the `ESC-T` shortcut.

##### Python Tool

![Python Tool Example](docs/images/tool-python.jpg "Python tool example")

The Python tool enables a model to execute Python scripts. To enhance security, the code runs within a Docker container, providing a level of isolation. The script can interact within the container and access the network.

In the screenshot above, the tool calls and responses are shown in the output. This is called "verbose mode" and can be toggled modified in the configuration via `chat.verbose` or toggle with `ESC-V` in the chat interface.

Due to potential security risks, the Python tool is disabled by default. To enable it, set `tools.python.enabled` to `true`. This can be configured using the `/set` command or by modifying `~/.lair/config.yaml`.

To use this tool, the user must have permission to run Docker containers, and Docker must be able to access or pull an appropriate image.

The `tools.python.docker_image` setting specifies which Docker image to use. By default, it is set to `python:latest`. Custom images can be used to include additional modules. For example:

```Dockerfile
FROM python:latest
RUN pip install numpy pandas requests
```

This image can then be built using a command such as:

```sh
docker build -t example-python:latest .
```

To use the custom image, update the configuration accordingly. The `tools.python.extra_modules` setting allows specifying additional packages, making them known to the language model in the tool description:

```yaml
tools.python.docker_image: 'example-python:latest'
tools.python.extra_modules: 'numpy, requests'
```

Python scripts will execute until they reach a timeout limit. The timeout duration is configurable via `tools.python.timeout` and defaults to 30 seconds.

##### Search Tool

![Search Tool Example](docs/images/tool-search.jpg "Search tool example")

The search tool utilizes the [DuckDuckGo](https://duckduckgo.com/) search engine to perform web and news searches. DuckDuckGo was selected because it does not require an API key for access. However, it does impose rate limits, so excessive search requests may require a cooldown period before additional searches can be completed.

This tool is enabled by default. To disable it, set `tools.search.enabled` to `false`.

The search function allows the module to query either web or news sources. The resulting URLs are processed sequentially, attempting to extract content from each page. If a page fails to load or does not provide usable content, the next URL in the list is tried. This continues until a sufficient amount of content is retrieved or no more URLs remain.

Web requests to retrieved URLs are subject to a timeout, which is configurable via `tools.search.timeout`. The default timeout is 5 seconds.

Search results can be large. To manage this, content extracted from each page is truncated based on the `tools.search.max_length` parameter. Additionally, the number of pages from which content is extracted is controlled by `tools.search.max_results`, which defaults to `5`.

The total amount of retrieved content can be as large as `max_results * max_length`, potentially exceeding the default context window of a language model. For users utilizing Ollama, the default context size is set to 2048 tokens. If this limit is exceeded, truncation may occur, leading to incomplete or inaccurate responses. To mitigate this, adjust the `num_ctx` parameter within Ollama as needed.

##### File Tool

The File Tool provides access to read and write files and directories on the local file system. This feature is **disabled by default** due to its potential risks.

⚠️ **DANGER:** This is an experimental feature. **Back up your files!** Running in a chroot environment or within Docker is strongly recommended to minimize risk. While some safeguards exist, they have not been thoroughly tested.

File access is limited to the path specified in `tools.file.path`. It is recommended to set this to a controlled directory containing only the files that should be accessible. Additionally, maintaining a separate full backup of this directory is advised.

To enable the File Tool, multiple configuration options must be set:
- `tools.allow_dangerous_tools` – Required to acknowledge the experimental and untested nature of this feature.
- `tools.file.enabled` – Enables basic read-only operations via `read_file` and `list_directory`.
- `tools.enable_deletes` – Enables file and directory deletion using `delete_file` and `remove_directory`.
- `tools.enable_writes` – Grants write access through `write_file` and `make_directory`.

The `tools.file.path` setting must also be configured with the path that should be made accessible.

Use caution when enabling these options, as they can modify or delete critical files.


##### Tmux Tool

The Tmux tool allows interaction with command-line applications via Tmux. Depending on enabled features, it can create windows, send input, read output (either as a stream or as a text "screenshot" of the current state), list windows, and terminate them. This capability enables LLMs to execute any command-line application, including shells. However, this feature is **disabled by default** due to potential risks.

⚠️ **DANGER:** This is an experimental feature. Running it in a chroot environment or within Docker is strongly recommended to minimize risks. Ensure you **back up any files it can access**. Granting root access is not advised.

Configuration settings for Tmux are found under the `tools.tmux.*` namespace. In addition to enabling `tools.tmux.enabled`, each tool requires specific flags to be activated.

| Tool              | Description                                       | Flags                                                         |
|-------------------|---------------------------------------------------|---------------------------------------------------------------|
| `attach_window`   | Attach to an existing window by ID                | `tools.tmux.attach_window.enabled`                            |
| `capture_output`  | Capture a text "screenshot" of the current window | `tools.tmux.capture_output.enabled`                           |
| `kill`            | Terminate a running window by ID                  | `tools.tmux.kill.enabled`                                     |
| `list_windows`    | List all windows in the session                   | `tools.tmux.list_windows.enabled`                             |
| `read_new_output` | Read new output as a stream                       | `tools.tmux.read_new_output.enabled`                          |
| `run`             | Create a new window                               | `tools.tmux.run.enabled`                                      |
| `send_keys`       | Send keyboard input to the window                 | `tools.tmux.send_keys.enabled`, `tools.allow_dangerous_tools` |

By default, if Tmux is enabled, the `run`, `capture_output`, and `read_new_output` commands are also enabled. This configuration effectively puts Tmux into a read-only mode, allowing it to create new windows and view their output but not send input or modify them. While limited, this mode can still be useful for running commands to retrieve system status.

All Tmux windows are placed in a session named by `tools.tmux.session_name` with a default of `lair`. To simplify management, each window supports only a single pane. Windows do not automatically close upon completion, as Lair cannot determine when they are no longer needed. To prevent resource exhaustion, you can set a maximum number of windows using `tools.tmux.window_limit`, which defaults to 25.

The `run` command launches a window executing a fixed command defined by `tools.tmux.run.command`. The command's description, provided by `tools.tmux.run.description`, helps the model understand its purpose. Using Docker or chroot is always recommended for security.

⚠️ **DANGER:** The window initially starts with a shell, and the command is executed as `exec {command}; exit`. This setup prevents access to the initial shell and ensures proper restriction enforcement. Be careful to keep the command proper so that restrictions are properly enforced. For those curious, this is done so that `pipe-pane` can be setup before the command runs and initial command output could be captured.

Here is an example configuration for the run command:

```yaml
tools.tmux.run.enabled: true
tools.tmux.run.command: 'docker run --rm -it local-example/nethack'
tools.tmux.run.description: 'This will launch the game Nethack.'
```

In this setup, no mechanism exists to automatically clean up the windows created. If commands do not exit or windows are not closed by the model, manual cleanup or external automation will be required.

**Output Handling:**

- The `capture_output` command returns a string of the entire pane's content. This is particularly useful for screen-based applications.
- The `read_new_output` command streams any new content since the last read or capture. By default, it returns the last `1024` bytes of new output, configurable via `tools.tmux.read_new_output.max_size_default`. The model can request more, up to the maximum specified by `tools.tmux.read_new_output.max_size_limit` (default `8192`).

The stream includes all window output (stdout, stderr, and echoed input). By default, user input is removed with `tools.tmux.read_new_output.remove_echoed_commands` (set to true). Escape sequences are also stripped unless configured otherwise via `tools.tmux.read_new_output.strip_escape_codes`.

**Log Management:**

All terminal output is saved to files in `~/.lair/tmux-logs/` by default. This path and filename can be configured using `tools.tmux.capture_file_name`. These log files are not automatically deleted and can be used for monitoring or as a record of terminal activity.


##### MCP Tool

The MCP tool allows Lair to dynamically load tools from remote providers following the
[MCP specification](https://github.com/openai/openai-cookbook/tree/main/examples/multi-tool-agent#mcp-specification).
When enabled, the MCP tool retrieves a manifest from one or more provider URLs.
Each provider is contacted via a JSON-RPC request with method ``tools/list``.
The available tools are registered from the manifest and become accessible just
like built-in tools.

MCP tools are disabled by default. To enable them, set ``tools.enabled`` and
``tools.mcp.enabled`` to ``true``. Provider URLs are specified one per line in
``tools.mcp.providers``. If changes are made on the provider side, run the
``/mcp-refresh`` command in the chat interface to reload the manifest. The
refresh output lists each provider URL with the number of tools found or
displays a warning when none are available.

The timeout for both manifest requests and tool calls is controlled by
``tools.mcp.timeout`` and defaults to ``10`` seconds.


#### One-off Chat

By lowering `session.max_history_length` to `1`, only the system prompt and the current message are provided, with no conversation history. This can be useful in scenarios where maintaining a conversation history is not desirable or when sending one-off requests.

```
crocodile> /prompt Respond with a snappy one-liner joke about the provided topic
crocodile> /set session.max_history_length 1
crocodile> Python programming language
Why did Python go to the beach? Because it heard the waves were "byte"ing!
crocodile> Go programming language
Why did Go to the beach? Because it heard the function was strong!
crocodile> Java programming language
Why did Java go to the doctor? Because it had a class problem!
```

#### Extracting Embedded Responses

The `/extract` command provides a quick way to retrieve specific sections of a response. By default, sections are defined as content within Markdown code blocks or between `<answer></answer>` tags. The definition of a section is configurable via the setting `chat.embedded_syntax_regex`. Any number of styles can be defined within the regex, but only the result of the first non-empty capture for each match is used.

The `<answer>` style is useful for responses where the LLM has been instructed to work through a process and write its final answer within tags. This is particularly helpful for chain-of-thought-style requests.

To demonstrate this, we'll first create a response with multiple code blocks. Markdown rendering is disabled for clarity in the response below:

~~~
crocodile> Please write hello world in Go, Rust, and Python. Only provide the language name followed by a codeblock for each. No explanation of comments are needed. Keep it brief.

Go
```go
package main

import "fmt"

func main() {
    fmt.Println("Hello, World!")
}
```

Rust
```rust
fn main() {
    println!("Hello, World!");
}
```

Python
```python
print("Hello, World!")
```
~~~

Now the `/extract` command can be used to pull out a specific code block. The syntax is `/extract [position?] [filename?]`. Position indexes start at 0 and 0 is the default.

```
crocodile> /extract
package main

import "fmt"

func main() {
    fmt.Println("Hello, World!")
}
```

Any section can be selected to return via its index.

```
crocodile> /extract 2
print("Hello, World!")
```

Negative indexes also work. For example `-2` references the second to last section.

```
crocodile> /extract -2
fn main() {
    println!("Hello, World!");
}
```

A second argument can specify a filename as a destination for writing out the section.

```
crocodile> /extract 0 ~/hello.go
Response saved  (76 bytes)
```

#### Modifying Chat History

Lair's chat interface provides several ways to view and modify chat history, making it easier to refine past interactions.

The chat history can be viewed in different formats. The `/history` command presents the chat in a formatted, readable manner, which may include markdown rendering, reasoning model formatting, and truncation, depending on configuration. For a raw data view, the `/messages` command displays the chat history as a JSONL-formatted list of message objects.

To remove specific messages from the history, use the `/history-slice` command. This command accepts Python-style slicing syntax (`start:stop:step`). Each section is optional. Start defaults to `0`, stop to the end of the sequence, and step to `1`. For example:

- `:4` retains only the first four messages. This is equivalent to `0:4:1`.
- `:-2` removes the last two messages while keeping the rest.
- `::2` keeps every other message, starting with the first.

For example, consider the following chat history:

```
crocodile> /messages
{"role": "user", "content": "Hi"}
{"role": "assistant", "content": "Hello there."}
{"role": "user", "content": "What is your name?"}
{"role": "assistant", "content": "My name is ChatBot."}
{"role": "user", "content": "If you could pick a new name, what would it be?"}
{"role": "assistant", "content": "I would pick Botty McBotface."}
```

Using `/history-slice` :-2 removes the last two messages. The slice `:-2` is a shorthand for `0:-2:1`, meaning it starts from the first element, stops at the second-to-last, and moves one step at a time.

```
crocodile> /history-slice :-2
History updated (Selected 4 messages out of 6)
crocodile> /messages
{"role": "user", "content": "Hi"}
{"role": "assistant", "content": "Hello there."}
{"role": "user", "content": "What is your name?"}
{"role": "assistant", "content": "My name is ChatBot."}
```

For more advanced modifications, the `/history-edit` command allows editing the chat history in an external text editor. The editor used is determined by `misc.editor_command`, or, if not set, the `VISUAL` or `EDITOR` environment variables.

When `/history-edit` is executed, the full chat history is loaded into a JSONL-formatted file where each line represents a message object following the OpenAI API format. This allows users to add or remove messages, as well as modifying any message content, including assistant responses

Since `/history-edit` loads the complete history without truncation, large files may result if attachments or tool calls are present.

### Model Settings

```
crocodile> /prompt Respond with a one-liner joke about the provided topic
crocodile> /set session.max_history_length 1

# Set temperature to 0.0 to make answers more deterministic
crocodile> /set model.temperature 0.0
crocodile> ducks
Why did the duck go to the doctor? Because it had quack-eyes!
crocodile> ducks
Why did the duck go to the doctor? Because it had quack-eyes!
crocodile> ducks
Why did the duck go to the doctor? Because it had quack-eyes!

# Set temperature to 1.0 to make them more random
crocodile> /set model.temperature 1.0
crocodile> ducks
Why did the duck cross the road? To get away from all the chicken questions!
crocodile> ducks
Why did the duck go to the doctor? Because it had a quack-attack!
crocodile> ducks
Why did the duck go to art school? To learn how to draw its life!
```

### File Based Session Management

This section provides examples of using file based session management. For a more general overview of sessions in Lair and the database-based session management, see [Session Management](#session-management).

File based session management allows for saving and loading a single serialized session to and from a JSON file. This is helpful for preserving exact sessions states, sharing sessions, quickly rolling back, etc.

The `/save` and `/load` commands are used for session management.

```
# Start a new session
crocodile> In 3 words or less, what is the meaning of life?
Find purpose and joy.
crocodile> In 3 words or less, how do I do that?
Define values, act.

# If no path is provided, files are saved to the current directory
crocodile> /save meaning_of_life.session
Session written to meaning_of_life.session

# Full paths as well as tilde expansion are also supported
crocodile> /save ~/meaning_of_life.session
Session written to /home/doug/meaning_of_life.session
```

The saved session can then be loaded with the `/load` command:

```
$ lair chat
Welcome to the LAIR
crocodile> /load meaning_of_life.session
Session loaded from meaning_of_life.session

# The history will continue where the saved session left off
crocodile> /last-prompt
SYSTEM: You are a friendly assistant. Be friendly,
and assist.
USER: In 3 words or less, what is the meaning of life?
ASSISTANT: Find purpose and joy.
USER: In 3 words or less, how do I do that?
```

Session files include the full active configuration. Loaded sessions will restore all the active settings. If this is undesirable, `/mode` or `/reload-settings` can be used after `/load` to change to different configuration.

When using `/load`, the current active session replaced with the loaded session. To load the session into a new session slot, first create a new one (such as with `C-X n`,) and then use `/load`.

### Calling Comfy Workflows

The `/comfy` command makes it possible to run ComfyUI workflows from the chat interface. This is a wrapper over the command line interface of the comfy sub-command and uses their options. For detailed help, see [the Comfy sub-command documentation.](#comfy)

To use this command, provide the same exact arguments that would provided after running `lair comfy`. For example:

```
sdxl> /comfy image -p 'a duck in space' -o space-duck.png
```

With a vision model, this could then be read back.

```
sdxl> /model llava:34b
sdxl> What's happening in this image? <<space-duck.png>>
In the image you provided, there is a realistic-looking animated duck depicted as if it were floating in space. The
background features planets and stars, which suggests that the setting is an outer space environment. This kind of
imagery might be used for humorous effect or as part of a creative concept, such as blending animal life with science
fiction elements.
```

The `/mode` command can be used with custom-defined modes to quickly jump between different models and their settings. The `--help` flags, such as `/comfy image --help` display the defaults for the current mode.

There are a couple known issues with this command. The output can be noisy due to issues with ComfyScript writing output with no options to turn it off. If debugging is enabled, all ComfyScript output is shown, otherwise it is partially muted. Some output is still displayed when threads writes output after workflows complete. On exit, sometimes the ComfyScript threads throw errors. This can cause extra output, but doesn't cause any actual harm.

## Comfy

The Comfy command makes it possible to use a [ComfyUI](https://github.com/comfyanonymous/ComfyUI) server to run workflows. Currently, image diffusion and image to video workflows are supported. Underneath, this command uses [ComfyScript](https://github.com/Chaoses-Ib/ComfyScript) to provide a nice Python interface over ComfyUI.

ComfyScript does have some issues where it's output is difficult to control.When using the `comfy` command, there may be extra output generated by ComfyScript which Lair is unable to hide. When ComfyScript encounters errors it catches them internally, and it isn't clear how the caller could view these errors. This means Lair will often be unable to display details of what caused errors. Running with `--debug` will sometimes show ComfyScript's internally printed errors.

### Workflows and Dependencies

The ComfyUI Server must have all required nodes installed to use any given workflow. The [ComfyUI Manager](https://github.com/ltdrdata/ComfyUI-Manager) provides an easy way to set things up. Be aware that installing nodes can introduce security issues. Running ComfyUI in an isolated fashion or with containers could help lower risks.

<table>
  <thead>
    <tr>
      <th>Workflow</th>
      <th>Description</th>
      <th>Based On</th>
      <th>Dependencies</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>hunyuan-video-t2v</td>
      <td>Hunyuan Video Text to Video</td>
      <td><a href="https://comfyanonymous.github.io/ComfyUI_examples/hunyuan_video/">ComfyUI's example workflow</a></td>
      <td></td>
    </tr>
    <tr>
      <td>image</td>
      <td>Image generation w/ LoRA support</td>
      <td>Comfy's default workflow</td>
      <td></td>
    </tr>
    <tr>
      <td>ltxv-i2v</td>
      <td>LTX Video Image to Video</td>
      <td><a href="https://github.com/Lightricks/ComfyUI-LTXVideo">ComfyUI-LTXVideo</a> and <a href="https://comfyanonymous.github.io/ComfyUI_examples/ltxv/">Comfy Lightricks LTX-Video Examples</a></td>
      <td>
        <ul>
          <li><a href="https://github.com/kosinkadink/ComfyUI-VideoHelperSuite">ComfyUI-VideoHelperSuite</a><br></li>
          <li><a href="https://github.com/kijai/ComfyUI-Florence2">ComfyUI-Florence2</a><br></li>
          <li><a href="https://github.com/Acly/comfyui-tooling-nodes">comfyui-tooling-nodes</a></li>
	    </ul>
      </td>
    </tr>
    <tr>
      <td>ltxv-prompt</td>
      <td>LTX Prompt Generation via Florence2</td>
      <td><a href="https://github.com/Lightricks/ComfyUI-LTXVideo">ComfyUI-LTXVideo</a> (prompt generation only)</td>
      <td>
        <ul>
          <li><a href="https://github.com/kijai/ComfyUI-Florence2">ComfyUI-Florence2</a><br></li>
          <li><a href="https://github.com/Acly/comfyui-tooling-nodes">comfyui-tooling-nodes</a></li>
	    </ul>
      </td>
    </tr>
    <tr>
      <td>upscale</td>
      <td>Enlarge Images and Improve Quality</td>
      <td></td>
      <td>
        <ul>
          <li><a href="https://github.com/Acly/comfyui-tooling-nodes">comfyui-tooling-nodes</a></li>
	    </ul>
      </td>
    </tr>
  </tbody>
</table>

### Comfy Usage & Examples

The `comfy` command provides distinct sub-commands for each supported workflow, each with its own flags and configuration options.

Flags offer a quick way to set common options but do not cover all available configuration settings. They act as shortcuts to simplify usage of the most frequently used settings. Configuration options can be set either through the configuration file or directly from the command line. For example, a sampler can be specified using `lair -s 'comfy.image.sampler=euler_ancestral' comfy image ...` or `lair comfy image --sampler euler_ancestral ...`. Flags take precedence over configuration settings.

The `comfy` module has two primary configuration options:
- **`comfy.url`**: Specifies the address of the ComfyUI server. By default, this is set to ComfyUI's standard local configuration, so most users running it locally won't need to modify this.
- **`comfy.verify_ssl`**: Determines whether SSL certificates are verified. This is enabled by default (`true`). When disabled, it allows communication with ComfyUI servers over HTTPS, even if the certificates are invalid.

Modes can be defined in the `~/.lair/config.yaml` file to store settings tailored to different use cases. Modes simplify workflows; for instance, `lair -M {mode} comfy ...` applies the settings associated with the specified mode.

All available flags can be listed by running `lair comfy {mode} --help`. Available settings are documented [here](lair/files/settings.yaml).

Some flags are shared across workflows:
- **`--repeat` / `-r`**: Runs the workflow a specified number of times. This differs from batch size; batches are processed simultaneously on the GPU, while repeats are executed sequentially. For image generation, the total number of images produced equals the batch size multiplied by the number of repeats.
- **`--output-file` / `-o`**: Specifies the filename for the output. For image workflows, the default might be `output.png`, but this can be overridden by configuration or this flag. If a single image is generated, the exact filename is used. For multiple images, the base name becomes a prefix followed by a zero-padded counter (e.g., `output000000.png`, `output000001.png`). When only a single file is being used, the special filename `-` sends the output to STDOUT. However, this is not currently recommended because ComfyScript also writes to STDOUT, which could cause extra output in the same stream.
- **`--comfy-url` / `-u`**: Specifies the address of the ComfyUI server. By default, this is `http://localhost:8188`.

When setting inputs for a workflow, it is important to use valid values. Many settings directly provide inputs for nodes. The ComfyUI web interface is the easiest way to determine valid values. If invalid values are provided, an error will occur. Note that ComfyScript may not always handle exceptions cleanly, which can prevent detailed error messages from reaching the main thread. Running with the `--debug` flag enables additional ComfyScript output, often providing helpful information for troubleshooting.

#### image - Image Generation

To generate a single image:

```bash
lair comfy image --prompt 'A cyberduck, flying through the matrix'
```

Assuming default configuration is used, that will attempt to use a Stable Diffusion 1.5 model and write output to `output.png`. Often times more settings are needed.

```bash
lair comfy image \
    --prompt 'A cyber-duck, flying through the matrix' \
    --model juggernautXL_juggXIByRundiffusion.safetensors \
    --output-height 1024 \
    --output-width 1280 \
    --sampler euler_ancestral \
    --scheduler sgm_uniform \
    --cfg 4 \
    --steps 30
```

If a collection of settings are likely to be used again, it might make sense to add them to `~/.lair/config.yaml` For example, the above settings (other than prompt) can be stored as a mode named `juggxl` by adding this:

```yaml
juggxl:
  _description: SDXL Image Generation with JuggernautXL
  comfy.image.model_name: juggernautXL_juggXIByRundiffusion.safetensors
  comfy.image.output_height: 1280
  comfy.image.output_width: 1280
  comfy.image.sampler: euler_ancestral
  comfy.image.scheduler: sgm_uniform
  comfy.image.cfg: 4
  comfy.image.steps: 30
```

When using the `juggxl` mode, the provided values are the new defaults. They can still be overridden, and the whole workflow with the defaults can be triggered easily, such as:

```bash
lair -M juggxl comfy image -p 'A cyber-duck, flying through the matrix'
```

![Cyberduck](docs/images/cyberduck.jpg "Cyberduck example - downscaled")

Some example modes for `sdxl` and `sdxl_lightning` are placed in the default `~/.lair/config.yaml` for convenience. To enable these, they must be un-commented. The examples reference specific models which must be available in ComfyUI or modified in order for them to work.

Any number of LoRAs may be specified in either the configuration or from the command line. If LoRAs are provided on the command line, any specified in the settings are overridden and ignored. LoRAs can be written either as `{name}`, `{name}:{weight}`, or `{name}:{weight}:{clip_weight}`. If `weight` or `clip_weight` are not included, the default of `1.0` is used.

On the command line `--lora` / `-l` may be provided multiple times. The LoRAs are used in the order provided.

```bash
lair -M juggxl comfy image \
    --prompt 'cute monsters at a dance party, detailed scene, detailed room, detailed background, paper cutout, pixel art' \
    --lora pixel-art-xl-v1.1.safetensors \
    --lora Neon_Cyberpunk_Papercut_2_SDXL.safetensors:1.1
```

To specify LoRAs within the settings, they should be written one LoRA definition per line in the YAML. For example, the above defintions would be:

```yaml
  comfy.image.loras: |
    pixel-art-xl-v1.1.safetensors
    Neon_Cyberpunk_Papercut_2_SDXL.safetensors:1.1
```

![Pixel Art Robot Dance Party](docs/images/pixel-robot-party.jpg "Robot Dance Party example - downscaled")

The `--batch-size` / `-b` and `--repeat` / `-r` options can be used to generate multiple images. The batch size determines how many images are generated on the GPU at a time, and the repeats are independent calls to the workflow. The total number of images is the batch size times the number of repeats. For example, the command below will generate 8 JPG images named `monster000000.jpg` through `monster000007.jpg`:

```bash
lair -M juggxl comfy image \
    --prompt 'cute monsters at a dance party, detailed scene, detailed room, detailed background, paper cutout' \
    --lora Neon_Cyberpunk_Papercut_2_SDXL.safetensors:0.6 \
    --batch-size 4 \
    --repeat 2 \
    --output-file 'monsters.jpg'
```

When scripting, combining with ImageMagick can be very powerful for automating edits of the images. For example, after running the above command:

```bash
montage monster*.jpg -tile 4x2 -geometry +0+0 monster-grid-full.jpg
convert monster-grid-full.jpg -resize 640x monster-grid.jpg
```

![Monster Dance Party Grid](docs/images/monster-grid.jpg "Monster Dance Party grid example - downscaled")

#### ltxv-i2v - LTX Video Image to Video

The `ltxv-i2v` workflow is based on the [ComfyUI-LTXVideo's](https://github.com/Lightricks/ComfyUI-LTXVideo) and <a href="https://comfyanonymous.github.io/ComfyUI_examples/ltxv/">Comfy Lightricks LTX-Video Examples</a> image to video workflows. It takes an image as input and then produces a video using LTX Video. The LTX Video model requires detailed prompts to work well. This workflow can automatically generate prompts using Microsoft's Florence2 model.

When automatic prompts are used, the prompt consists of 3 parts. First, there is the automatic prompt generated by Florence2. After that, extra details could be added via `--auto-prompt-extra` / `-a`. Finally, there is a suffix, which can be set via `--auto-prompt-suffix` / `-A`. The default suffix is `The scene is captured in real-life footage.`. That might change in the future. The ComfyUI-LTXVideo prompt uses that as a default, but also recommends `The scene appears to be from a movie or TV show` and `The scene is computer-generated imagery` where appropriate.

If a prompt is provided via `--prompt` / `-p`, `--prompt-file` / `-P`, or the `comfy.ltxv_i2v.prompt` setting, then that prompt will be used as-is, and no automatic prompt generation will be performed.

The most basic usage requires only an image to be provided.

```bash
lair comfy ltxv-i2v --image example.png
```

This will build a prompt automatically based on `example.png` and then generate an `output.mp4` file.

This workflow has many parameters. Configuration options can be found [here](lair/files/settings.yaml), and modes can be created to automatically use different settings. The `comfy ltxv-i2v` sub-command also provides a number of helpful flags for common options. Run `lair comfy ltxv-i2v --help` to see all available flags.

The seed for the Florence model is fixed by default. It could be made random by setting `comfy.ltxv_i2v.florence_seed` to null, but doing so disables caching. When random, every run of the workflow will generate a new prompt. When the seed is fixed, the cached results are used allowing it to skip the extra inference and speed up the workflow.

The output formats can be set through `--output-format` / `-O` or `comfy.ltxv_i2v.output_format`. By default, `video/h264-mp4` is used, but any option available in the Comfy VHS Video Combine node should work. Some others include `image/gif`, `image/webp`, and `video/webm`. When changing the output format, the output file's extension should also be updated to match.

This workflow combines really nicely with the `image` workflow. For example, using bash:

```bash
# Generate 8 monster JPGs
# See the image documentation above for the example `juggxl` mode's configuration.
lair -M juggxl comfy image \
    --prompt 'cute monsters at a dance party, detailed scene, detailed room, detailed background, paper cutout' \
    --lora Neon_Cyberpunk_Papercut_2_SDXL.safetensors:0.6 \
    --repeat 8 \
    --output-file 'monster.jpg'

# For each JPG file, create a video file
for filename in monster*.jpg; do
    lair comfy ltxv-i2v -i "${filename}" -o "${filename%.jpg}.mp4"
done
```

A similar technique was used to create [this video](https://youtube.com/shorts/XdiFj1qDIqk).

#### ltxv-prompt - LTX Video Prompt Generation via Florence2

This workflow is based on the [ComfyUI-LTXVideo's](https://github.com/Lightricks/ComfyUI-LTXVideo) image to video workflow, but it only performs prompt generation. It takes an image for input, and outputs the text of the prompt generated from the Florence2 model.

The LTXV model requires very detailed prompts to work well. While the official workflow uses Florence2 for prompt generation, the prompts it generates are often in need of further refinement. Using `ltxv-prompt` makes it possible to generate a prompt, edit it by hand, and then use that for future runs.

By default, `ltxv-prompt` will write to an output file such as `output.txt`. It is possible to specify the filename of `-` to write to STDOUT, but this currently isn't recommended. ComfyScript's threads write to STDOUT as well, and until that is fixed or fully silenced extra output might be mixed in.

```bash
# For this example, lets generate an image of a duck in a space suit
$ lair -M sdxl comfy image -p 'A duck in a space suit' -o duck.png

# The generated image can be passed to ltxv-prompt to generate a prompt
$ lair comfy ltxv-prompt -i duck.png

# By default, the prompt is written to output.txt
$ cat output.txt
The video shows a stuffed toy duck wearing a white space suit with an American flag on it. The duck is wearing a helmet with a blue visor and has a yellow beak. The background is a dark space with a circular window on the left side. The overall theme of the video is space exploration and exploration. The scene is captured in real-life footage.
```

The `output.txt` can now be modified by hand and then used for video generation:

```bash
lair comfy ltxv-i2v \
    --prompt-file output.txt \
    --image output.png
```

#### hunyuan-video-t2v - Hunyuan Video Text to Video

Tencent's [Hunyuan Video model](https://github.com/Tencent/HunyuanVideo) is supported natively in ComfyUI, meaning no additional third-party nodes are needed for setup or usage. For installation notes and model links, see the [Comfy Examples](https://comfyanonymous.github.io/ComfyUI_examples/hunyuan_video/) page for Hunyuan Video. The workflow used by `hunyuan-video-t2v` is based on ComfyUI's example, and shares many of its defaults.

Configuration can be found underneath `comfy.hunyuan_video.*`. All available options are documented [here](lair/files/settings.yaml).

Many command line options are supported. Run `lair comfy hunyuan-video-t2v --help` for the full list.

This workflow defaults to using tiled decoding. For most users, tiled decoding is necessary to reduce the VRAM requirements, but it may also impact performance and quality. If enough VRAM is available, it is usually best to disable tiled decoding. For smaller tasks, such as image generation, it often makes sense to disable it.  Tiled decoding behavior can be changed via the config `comfy.hunyuan_video.tiled_decode.enabled` flag, and the decoding parameters can all be found under `comfy.hunyuan_video.tiled_decode.*`.

To generate a video, at a minimum it usually is necessary to provide a prompt:

```sh
# Generate a video
$ lair comfy hunyuan-video-t2v \
    -p 'Video of a penguin playing saxaphone on the ice at night. Stars and moon in the sky.'
```

The above command will generate an `output.webp` file by default. The `--output-file` / `-o` flag can be used to specify an alternate filename as well as the `comfy.hunyuan_video.output_file` configuration option. When generating multiple files, such as with the `--repeat` / `-r` or `--batch-size` / `-b` options, the base name becomes a prefix followed by a zero-padded counter (e.g., `output000000.webp`, `output000001.webp`).

This workflow currently only supports generating `webp` files as output. This is a limitation from ComfyUI's workflow and more options may be added in the future. Many tools don't natively support decoding `webp` files. Here are a couple examples of how to convert to better supported formats.

```sh
# Use ImageMagick to create an animated GIF
# GIFs will always have lower quality
$ convert output.webp output.gif

# Use ImageMagick to extract frames into individual files, and then ffmpeg to convert to another format
$ convert output.webp -coalesce frame_%04d.png
$ ffmpeg -i frame_%04d.png -c:v libx264 -pix_fmt yuv420p output.mp4
```

The Hunyuan Video model can be used to generate individual images by setting `comfy.hunyuan_video.num_frames` to `1`, or by using `--num-frames` / `-F`.  For example:

```sh
# Generate a video
$ lair comfy hunyuan-video-t2v \
    --prompt 'Video of a penguin playing saxaphone on the ice at night. Stars and moon in the sky.' \
    --num-frames 1
```

The number of frames must be `N * 4 + 1`, such as 73, 77, 81. This requirement ensures smooth interpolation and alignment within the model's architecture, as frame counts outside this pattern may cause unexpected behavior or poor quality results.

LoRAs are supported, and multiple LoRAs could be provided. For usage examples, see the [Image Generation](#image---image-generation) section, as the behavior is identical.  The config key `comfy.hunyuan_video.loras` can be used to create modes with LoRAs or LoRA chains.


#### upscale - Enlarge Images and Enhance Quality

Upscale models can be used to enlarge images and enhance their quality by generating additional details based on learned patterns from other images. This is useful for sharpening images and improving quality.

ComfyUI natively supports various upscale models. To utilize this feature, an upscale model must be placed in ComfyUI’s `upscale_models/` directory. Many models are available at [OpenModelDB](https://openmodeldb.info/).

**Configuration**

Upscale settings are managed under the `comfy.upscale.*` namespace. The default model is `RealESRGAN_x2.pth`, which can be changed via `comfy.upscale.model_name`.

Each upscaled image is saved as a new file, with the filename determined by `comfy.upscale.output_filename`. This is a Python format string that should include the `{basename}` variable, which represents the original file path without its extension. For example, if the setting is `{basename}-upscaled.png`, then an image located at `foo/bar.png` will be upscaled and saved as `foo/bar-upscaled.png`.

**Usage Examples**

```sh
# Upscale an image using the default model
$ lair comfy upscale images/example.png

# Upscale multiple images
$ lair comfy upscale images/example.png images/example2.png other/*.jpg

# Use a specific upscale model
$ lair comfy upscale -m my_model.pth images/example.png

# Avoid overwriting existing files
$ lair comfy upscale --skip-existing images/example.png
```

**Processing Directory Trees**

The `--recursive` / `-r` flag enables recursive processing of directory trees. Only image files with supported extensions (`.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp`) will be included.

```sh
# Upscale all images in a directory and its subdirectories
$ lair comfy upscale --recursive images/
```

#### outpaint - Extend Images

Outpainting expands an image by generating new content outside of its
original borders. It uses an inpainting model and requires specifying how
much padding to add around the source image.

**Configuration**

Settings are under the `comfy.outpaint.*` namespace and include options for
padding, sampler, scheduler and other diffusion parameters. The `--denoise`
flag controls how strongly the outpainted area is blended with the original
image.

**Usage Example**

```sh
$ lair comfy outpaint example.png
```

### Example

Starting with this painting of Benjamin Franklin:

![start](https://github.com/user-attachments/assets/52b9d329-6359-4d6f-8a35-1e4b36291383)

We can grow the sides and the bottom and give him some food:

![start-outpainted](https://github.com/user-attachments/assets/2670d060-b1bd-4d3c-9dc0-7278346abbba)

Models seem to have a sweet spot of input sizes they work well with, and they often do better with multiple smaller outpainting steps instead of big jumps. The above was generated by running a small script for a few cycles that resizes the new result back down. The rescaling each cycle definitely harms the quality. While there are better techniques, at the current time Lair might choose not to support them natively. Here is an example script that was used to generate the above image.

```sh
#!/bin/bash

set -ex
convert benjamin.jpg -resize x768 start.png

while true; do
    lair comfy outpaint start.png \
         -R 0x32x64x32 \
         -g 16 \
         -f 64 \
         -p 'Seamless scene of Ben Franklin sitting in chair, cheeseburger, french fries, soda with straw' \
         -n 'frame, border'
    convert start-outpainted.png -resize x768 start.png
done
```

## Util

The `util` command provides a simple interface for calling LLMs. It is intended for one shot tasks and for making LLMs easy to work with in the shell and scripts.

The system prompt for the `util` command can be customized by setting `util.system_prompt_template` in the configuration. For tasks that require distinct instructions, it may be beneficial to define separate modes, each with its own dedicated system prompt.

By default, the `util` command does not render markdown, and the system prompt discourages markdown formatting unless explicitly requested. When the `--markdown` / `-m` flag is used, the system prompt permits markdown output, and the final response is rendered accordingly.

### Util Examples

#### Generating Content

The `util` command can be used to create content very easily. For example, to create some CSV test data:

```bash
$ lair util \
    -i 'Output CSV with 10 rows of test data using the following fields: first name, last name, address, zip code, phone number (w/ <area code)'
John,Doe,123 Elm St,12345,(555)123-4567
Jane,Smith,456 Oak Ave,67890,(555)987-6543
Alice,Brown,789 Pine Rd,54321,(555)555-5555
Bob,Green,321 Maple St,98765,(555)111-2222
Charlie,White,654 Birch Ave,43210,(555)333-4444
Diana,Yellow,987 Cedar Rd,87654,(555)666-7777
Eve,Purple,234 Spruce St,32109,(555)888-9999
Frank,Orange,567 Willow Ave,21098,(555)444-3333
Grace,Blue,890 Fir Rd,10987,(555)777-6666
Hannah,Pink,109 Hemlock St,98760,(555)222-1111
```

This feature can also be used to write simple programs, making it especially useful for one-off tasks like converting a CloudFront logfile to JSON format. For example, to create a tool to display the current time in different time zones:


```bash
$ lair util -i 'Write a python script that outputs the current time in UTC, California, New York, London, and Tokyo' > times.py

$ cat times.py
from datetime import datetime
import pytz

time_zones = ['UTC', 'America/Los_Angeles', 'America/New_York', 'Europe/London', 'Asia/Tokyo']

for zone in time_zones:
    tz = pytz.timezone(zone)
    current_time = datetime.now(tz)
    print(f"{zone}: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")

$ python times.py
UTC: 2024-12-26 20:05:28
America/Los_Angeles: 2024-12-26 12:05:28
America/New_York: 2024-12-26 15:05:28
Europe/London: 2024-12-26 20:05:28
Asia/Tokyo: 2024-12-27 05:05:28
```

In the above examples, instructions were provided using the `--instructions` / `-i` flag. Alternatively, instructions can be provided from a file using the `--instructions-file` / `-I` flag.

```bash
$ cat > instructions << EOF
Write a limerick about about a lousy AI tool called Lair. Be sure to have the correct rhyme scheme and number of syllabels per line for a limerick.
EOF

$ lair -s model.temperature=0.65 util -I instructions
There once was a tool named Lair,
Whose code was quite unclear.
It gave wrong advice,
In every single device,
Now its users just sigh with despair.
```

#### Providing Input Content

The `util` command can operate on content, which could be provided a few different ways. The `--content` / `-c` flags allow providing the content as a string on the command line. The `--content-file` / `-C` flags provide the specified file as content. The `--pipe` / `-p` flags read the content from stdin.

Here is an example of using an LLM to look at the `/etc/passwd` file and throw warnings on anything unusual.

```bash
$ lair util -C /etc/passwd -i 'An /etc/passwd file is provided. For each unusual or possible security issue found, write "WARNING:" followed by a summary. If there are no issues write only "No issues found"'
WARNING: User 'polkitd' has a home directory set to '/' which is unusual.
WARNING: User 'hack' has a shell set to '/bin/bash', which could be a security risk if not properly managed.
```

Here is an example of using the `--pipe` / `-p` flags to examine output from a command:

```bash
$ netstat -nr | lair util -p -i 'Please summarize this routing table in plain english'
All traffic is routed through gateway 10.0.1.1 on interface wlo1, except for local network 172.17.0.0/16 which uses docker0 and local network 10.0.1.0/24 which also uses wlo1.
```

#### Attaching Files

The `--attach-file` / `-a` flag allows for attaching one or more files. Multiple files could be provided via either globbing or by repeating `--attach-file` argument. Globbing and homedir expansion (`~`) is performed automatically. Globs might need to be protected to prevent the shell from expanding them.

Attachments can be image files, text files, or PDFs. For more details, see the [documentation](#attaching-files) for attaching files within the chat interface.

PDF files are converted to text without any images. Any number of files can provided, within the context length limits for the model.

```sh
$ lair -m llama3.2:3b-ctx0 util \
    -a ~/files/tos.pdf \
    -i 'List out anything worrisome or unusual from the provided terms of service'
* The inactivity disconnect policy after 15 minutes of inactivity.
* Automated processes are not allowed to maintain constant connections (section 3a).
* ISP has the right to audit connections to enforce terms (section 13b).
```

Image files only work properly with vision models. Here is a simple example, providing an image and asking for a summary.

```bash
$ lair -m llama3.2-vision:11b util \
    -i 'Provide an accurate oneliner description for each of the provided images. Max 60 characters.' \
    --attach-file electron_microscopy.png
A microscopic view of an electron microscope.
```

Multiple images can be provided at once with globs, such as `--atach-file \*.png`. By default, the model is not passed the filenames. In the example below, the `--include-filenames` / `-F` flag is used to enable sending the filenames with each image.

```bash
$ lair -m llama3.2-vision:11b util \
    -i 'Provide an accurate oneliner description for each of the provided images. Max 60 characters. output format: {filename}: {description}' \
    --attach-file \*.png \
    --include-filenames
electron_microscopy.png: A microscopic view of an electron microscope.
fantasy_art.png: A fantastical painting of a woman in a forest.
fractal_thanksgiving.png: A fractal image of a turkey on Thanksgiving.
stained_glass.png: A stained glass window depicting a floral pattern.
```

Unfortunately, models may get confused when provided multiple images. That should improve in the future, but for now, a safer (and slower) alternative might be to run the command once per image. This also makes the prior example possible without providing the filenames, which definitely biased the previous responses. For example:

```bash
$ for file in *.png; do
    echo "${file}: $(lair -m llama3.2-vision:11b util \
                         --attach-file $file \
                         -i 'Provide an accurate oneliner description of the provided image. Max 60 characters.')";
done
electron_microscopy.png: Virus cell.
fantasy_art.png: Serene mountain landscape with castle and garden.
fractal_thanksgiving.png: A pie decorated to look like a turkey with corn and cranberries.
stained_glass.png: Colorful stained glass window.
```

Note, the `Max 60 characters` instruction isn't followed by most current models. LLMs aren't that precise. Giving specific numbers like that nudges it in a direction, but doesn't introduce an actual limit.

#### Using Tools

The `--enable-tools` (`-t`) flag allows the model to invoke tools when using the `util` command. When this flag is enabled, `tools.enabled` is automatically set to `true`, but individual tools must still be explicitly enabled in the configuration for them to be available.

For more information on using tools within Lair, available tools, and setup instructions, refer to the [Tools Documentation](#tools) in the Chat section.

The following example demonstrates using the search tool to retrieve recent news results:

```sh
$ lair --model llama3.2:3b-ctx0 util \
        -i 'New AI news. Reply format: - {date,YYYY-MM-DD}: {headline}' \
        --enable-tools
- 2025-02-05: TikTok Owners New AI Tool Makes Lifelike Videos From A Single Photo
- 2025-02-06: Palantir On Verge Of Exploding With Powerful Reasoning AI
- 2025-02-06: Reframing digital transformation through the lens of generative AI
- 2025-02-06: UB study finds framing can boost employee confidence in AI, but one big error can destroy it
- 2025-02-06: Workday lays off 1,750 employees, or about 8.5% of its workforce in AI shift
- 2025-02-06: New Teladoc, same acquisition strategy
```

Specifying `--model` is optional. However, in this example, a locally modified `llama3.2:3b` model was used with Ollama to extend the context window via `num_ctx`. By default, Ollama uses a context size of 2048, which may be insufficient for search-based tasks. For guidance on configuring the search tool, see the [Search Tool Documentation](#search-tool).

The Python tool allows the model to generate and execute Python code within a container, retrieving the results. This tool is disabled by default. For instructions on enabling and configuring it, refer to the [Python Tool Documentation](#python-tool).

```sh
$ lair util -i 'Use Python to GET whatismyip.akamai.com, and return the IP' -t
255.1.2.3
```

*Note:* The IP address shown above is a placeholder. The actual output has been replaced for privacy reasons.

The `--debug` flag can be added before `util` to enable detailed output, displaying all requests and responses. In the Python tool example, a common behavior is for the model to first attempt using the `requests` library. If `requests` is not installed, it encounters an error and retries using `urllib`. This additional cycle can be avoided by explicitly specifying `urllib` in the instructions or by using a custom Docker image that includes `requests` pre-installed.

#### Using Sessions

The `util` command fully supports sessions from the session database used by the `chat` command. For a more complete overview of sessions, see the [Session Management](#session-management) section.

The `--session` / `-s` flag allows specifying a session ID or alias. For example, if session `1` contains a discussion about naming a metasyntactic variable, we can retrieve that information like this:

```sh
$ lair util -s 1 -i 'What was the variable name we decided on?'
foobar
```

The `--allow-create-session` / `-S` flag modifies session behavior by automatically creating a new session if the specified ID or alias does not exist. The given value then becomes the alias for the new session. This makes it easy to maintain persistent command-line conversations.

```sh
$ lair util -S -s fizzbuzz -i "Let's play fizzbuzz. Please respond with the first number"
1
$ lair util -S -s fizzbuzz -i "Next number please"
2
$ lair util -S -s fizzbuzz -i "Next number please"
Fizz
$ lair util -S -s fizzbuzz -i "Next number please"
4
$ lair util -S -s fizzbuzz -i "Next number please"
Buzz
```

Sessions created this way are also accessible in the chat interface:

```sh
$ lair chat -s fizzbuzz
Welcome to the LAIR
crocodile:2> /session
┏━━━━━━━━┳━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ active ┃ id ┃ alias    ┃ mode      ┃ model             ┃ title                ┃ num_messages ┃
┡━━━━━━━━╇━━━━╇━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│        │ 1  │          │ crocodile │ qwen2.5-coder:32b │ Variable Naming Help │ 6            │
│ *      │ 2  │ fizzbuzz │ crocodile │ qwen2.5-coder:32b │ FizzBuzz Game Start  │ 10           │
└────────┴────┴──────────┴───────────┴───────────────────┴──────────────────────┴──────────────┘
crocodile:2> /last-response
Buzz
```

By default, session history appends new queries and responses. If you want to query a session without modifying it, use the `--read-only-session` / `-r` flag.

For example, let’s create a new session named `cnn-demodulation` and attach a [paper](https://arxiv.org/abs/2502.19097) from arXiv:

```sh
$ lair \
    -m llama3.2:3b-ctx0 \
    util \
    --allow-create-session \
    --session cnn-demodulation \
    -a ~/2502.19097v1.pdf \
    -i 'Please summarize the conclusions of this paper briefly'
The use of a convolutional neural network (CNN) for demodulating weak JT65A signals achieves acceptable performance, with the interference immunity being about 1.5 dB less than the theoretical limit for non-coherent demodulation of orthogonal MFSK signals.
```

Now, we can use `--read-only-session` / `-r` to ask further questions without modifying the session. Since the paper is already in context, this avoids unnecessary additions to the session history.

⚠️ **Do not include the `--attach-file` / `-a` flag in follow-up queries**, as this would re-upload the same content.

```sh
$ lair -m llama3.2:3b-ctx0 util -S -s cnn-demodulation -r \
    -i 'What is the accuracy of this technique'
The proposed method achieved an error rate of 10^-2 or lower, indicating high accuracy in demodulating JT65A signals. The symbol error rate against SNR showed that the proposed method outperformed the theoretical limit of non-coherent demodulation of orthogonal FSK signals for 1.5 dB.
```
