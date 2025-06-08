# WIP - v0.8.2+dev

### Bug Fixes
- comfy: Fix `ltxv-i2v` default model version
- util: Fix issue where image attachments stopped working
- comfyscript: Restart watch thread correctly
- comfyscript: Reuse a persistent event loop to avoid delays between calls

### New Features
- comfy: Add `outpaint` workflow for extending images
- comfy: Add `--denoise` option for outpainting

### Internal
- documentation: Add AGENTS.md and introduction video link
- tests: Add pytest suite and extended chat interface coverage
- docker: Add lair into youtube image
- deps: Replace pyflakes with ruff for linting
- deps: Add `rich` to dev dependencies for testing
- documentation: Expand README outpainting example
- tests: Add coverage for all chat sub-commands
- tests: Add completer, attachment, and argument parsing coverage
- documentation: Update AGENTS instructions to use Poetry

# v0.8.1 - Bug fixes

### Bug Fixes
- comfy: Fix issue in chat where changes to `comfy.url` are not propagated on mode switch
- comfy: Fix upscale help message inaccurately claiming model is required
- config: Fix broken mode inheritance when inheriting from multiple modes


# v0.8.0 - New /list-settings command, bugfixes

### Changes
- chat: Add `/list-settings` command with search, baseline compare, and only-show diff options
- chat: Add output message when running `/clear` for consistency `with c-x c`
- chat: Pressing tab while at the sessions switch prompt now shows all sessions

### Bug Fixes
- Fix errors from inconsistent types between Ollama OpenAI endpoints and real OpenAI
- Fix schema strictness issue where null tool call "index" values were not allowed


# v0.7.0 - Tmux Tool, LTXV 0.9.5 support, many small improvements

### Changes
- New tool: TmuxTool allows for interacting with command line applications
- chat: Add colors and better sorting to Tools report
- chat: Highlight active model in `list-models` report
- chat: Improve sorting in modes report and highlight active instead of using a `*`
- chat: Remove sessions report active column and highlight active id
- chat: Show `0` messages in the sessions report with a dark gray color
- chat: The `/session-delete` command now supports `all` as an id to remove all sessions
- comfy: `ltxv_i2v` workflow is updated for compatibility with LTXVideo 0.9.5
- docs: Adjusted README.md headers to reduce document depth
- file_tool: Support reading multiple files in one request with globs (#14)

### Bug Fixes
- Fix issue where automatic title generation fails if it uses a tool message (#13)
- README.md: Fix badly rendered table from github-flavored markdown glitch
- chat: Fix bug where `/set` fails to cast bools with extra space
- chat: Fix error on autocomplete for `/set` with null current values
- chat: Fix error when switching back to a deleted session
- comfy: Fix bad help message for `ltxv_i2v`
- comfy: Fix config values that broke in the config system overhaul
- docs: Fix incorrect chat command optional flags
- tools: Fix incorrect response to invalid tool calls

### Breaking Changes
- ltxv-i2v is a new workflow with config parameter changes and flag changes

### Internal
- internal: Refactored how tools are initialized to improve reusability and testing (#17)
- internal: Rename reporting's `plain()` to `style()` for clarity

# v0.6.1 - Bug Fixes: Dependency & Tools Issues

### Bug Fixes
- fix missing lmdb dependency
- tools: Fix config error from flags misuse


# v0.6.0 - Session Management, Keyboard Shortcuts, FileTool, History Editing

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

### Bug Fixes
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

### Changes
- config: `debug.verbose` is now `chat.verbose`  (previously unused leftover from langchain verbose)

### Bug Fixes
- core: Fix issue where overrides for individual settings overrides weren't propagating to the comfy defaults
- reporting: Fix issues with table generation when all columns aren't used
- util: Fix issues when launching without attachments

### Breaking Changes
- chat: The bottom toolbar is now toggled with `ESC-B` instead of `ESC-T`


# v0.4.0 - PDF and text attachments, reasoning models

### New Features
- add support for PDF and text attachments to `chat` and `util`
- add support for styling reasoning model thought tag output

### Bug Fixes
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

### Bug Fixes
- fix debug checks to be for all log levels inclusive of debug, instead of only debug

### Internal
- new function: `lair.config.get()`, to simplify retrieving settings without having to specify the active mode
- settings.yaml: Fixed issues with section ordering


# v0.1.0 - Initial Release w/ Chat & Util Modules

### New Features
- add `chat` module, w/ auto-complete, file based sessions, & markdown rendering
- add `util` module for CLI scripting with image support
