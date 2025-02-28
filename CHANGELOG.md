# WIP: v0.6.0 - Session Management, Keyboard Shortcuts, FileTool, History Editing

### New Features
- chat: Add support for editing history via slices
- chat: Add support for editing history with an external editor
- chat: Added debug mode toggle (ESC-D)
- chat: Added keys for managing sessions (new, next, previous, reset, show, switch)
- chat: Added keys for showing models and tools reports
- chat: All keybindings are now configurable (via chat.keys.*)
- chat: F1 through F12 quick-switch to sessions 1 through 12
- chat: Key toggles display system messages instead of flashing the toolbar
- chat: Multi-session support
- chat: New commands for managing sessions
- chat: New template variables: `session_id`, `session_alias`
- sessions are now persisted into an LMDB
- support automatic title generation for sessions (configured via session.auto_generate_titles.*)
- tools: Add in new File Tool for working with files on the local filesystem
- util: Add `--markdown` flag for requesting and rendering markdown output
- util: Support for creating or using existent sessions

### Changes
- chat: The default prompt and toolbar now include the session id
- config: Remove old database.* keys and add new ones for the sessions database
- documentation: Many cleanups

### Bugfixes
- fix invalid openai max retries and timeout values
- fix issue where SSL verification was performed even when disabled in ComfyScript
- fix issue where template variable model could ignore overrides
- fix issue where model overrides could be ignored
- probably a lot of others!

### Internal
- add new v0.2 serialization format
- overhauled config, removing mode parameters and making mode defaults immutable to simplify
- overhauled events system and added support for event deferment and automatic deregistration

### Breaking Changes
- the v0.1 session format is no longer supported


# v0.5.0 - Tools, Hunyuan Video, and image upscaling

### New Features
- prompts are now Jinja2 templates and stored in the configuration
- chat: Add auto-complete for `/prompt`, making it much easier to edit prompts
- chat: Added support for tools
- chat: New /`messages` command displays or saves JSONL messages output
- chat: New `/list-tools` command shows available tools and their status
- chat: New `ESC-T` shortcut to toggle tools
- chat: The `/set` and `/prompt` command now properly support newlines, multiline input, and repeat spaces
- chat: Verbose mode now supports showing tool calls/responses
- comfy: Add Hunyuan video text to video support (`comfy hunyuan-video-t2v`)
- comfy: Add image upscaling support (`comfy upscale`)
- tools: Added Python tool for executing python code in a container
- tools: Added Search tool for searching DuckDuckGo for web or news results
- util: Added `-t` / `--enable-tools` flag to run utilities with tools

### Bugfixes
- config: `debug.verbose` is now `chat.verbose`  (previously unused leftover from langchain verbose)
- core: Fix issue where overrides for individual settings overrides weren't propagating to the comfy defaults
- reporting: Fix issues with table generation when all columns aren't used
- util: Fix issues when launching without attachments

### Breaking Changes
- chat: The bottom toolbar is now toggled with `ESC-B` instead of `ESC-T`


# v0.4.0 - PDF and text attachments, reasoning models

### New Features
- add support for PDF and text attachments to `chat` and `util`
- add support for styling reasoning model thought tag output

### Bugfixes
- fix issue where history could be appended to, even on chat failures


# v0.3.0 - New chat commands & quality of life improvements

### New Features
- chat: Add `/comfy` command, allowing ComfyUI workflows to be called from the chat interface
- chat: Add `/extract` command, allowing for extracting content from response sections (such as code blocks)
- chat: Add `/list-models` command, providing a list of available models
- chat: Add auto-complete to `/models` based on available models
- chat: Add support for `/last-prompt` and `/last-response` to save to a file
- chat: Support external command registration, allowing other modules to add commands to chat
- config: Add `_inherit` property, allowing config sections to inherit from other sections

### Changes
- docs: Many cleanups, fixes, and refactors


# v0.2.0 - Support for Comfy Workflows

### New Features
- add `chat.attachments_enabled` setting to allow for disabling attachments
- add `chat.attachments_syntax_regex` to allow for customizing the syntax
- comfy: Add workflow `image` for basic image diffusion
- comfy: Add workflow `ltxv-i2v` for LTX Video image to video
- comfy: Add workflow `ltxv-prompt` for creating video prompts from Florence2
- config files now support an _inherit attribute which contains a list of other modes to inherit from (experimental)
- new `comfy` sub-command for running ComfyUI workflows

### Changes
- chat file attachment syntax now uses doubled angle brackets `<<~/file.png>>`
- config.yaml: Added sdxl and sdxl_lightning example configs (commented by default)

### Bugfixes
- fix debug checks to be for all log levels inclusive of debug, instead of only debug

### Internal
- new function: `lair.config.get()`, to simplify retrieving settings without having to specify the active mode
- settings.yaml: Fixed issues with section ordering


# v0.1.0 - Initial Release w/ Chat & Util Modules

### New Features
- add `chat` module, w/ auto-complete, file based sessions, & markdown rendering
- add `util` module for CLI scripting with image support
