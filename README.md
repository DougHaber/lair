# LAIR

## Overview

Lair is a set of utilities and tools for working with generative AI. This repository contains an open source version of Lair. The open source version currently provides some general purpose functionality, such as a command line chat interface and a one-off utility command.

The full lair repository has various other features such as an agent framework, tools for evolutionary programming with LLMs, and a tool for creating non-temporal videos from image diffusion models. Some hints of other features might still exist in the code, but a lot of modules were not included. If there is interest, over time I might add some of the other functionality into the open source version.

## Features

* **chat**: Command line chat interface
  * Rich interface w/ auto-complete, commands, shortcuts, etc
  * File based session management
  * Support for image file attachments
  * Markdown rendering & syntax highlighting

* **util**: Unix-style utility for scripting or one-off LLM usage
  * Simple I/O for sending content via file or pipes to LLMs
  * Support for image file attachments

## Future

As this is a hobby project, there is no roadmap or guarantee that anything will be addressed, but these are the next big features and fixes I'd like to see added in:

* Support for attaching other formats, such as PDF and TXT files.
* Support for tools in chat. This existed in an older unreleased version of lair, but a refactor removed langchain, and with it tools support.
    * A search tool should be added, allowing the LLM to use a search engine and read the results.
* Support for external sub-command and module loading.

## Installation

Lair is installed as a Python command, requiring Python 3.10 or greater to be installed. Any Python package management tool could install lair (such as pip, pipx, and uv.) For most users, pipx or uv are probably the best options.

```sh
pipx install git+https://github.com/DougHaber/lair.git@0.1.0
```

Replace `0.1.0` with the latest version. The `master` branch will contain the latest unreleased version. Official releases will be tagged using semantic versioning.

## Configuration

In Lair, configuration is a set of namespaced key value pairs. All pairs could be found [here](lair/files/settings.yaml). Types are enforced and attempting to set a key to a different type of value will result in an error.

When lair is first run it will create `~/.lair/config.yaml`. Within this file, modes can be defined to which enable different settings. A mode is a named collection of settings. Modes can be used to jump between different configurations very quickly. The top level `default_mode` key allows specifying the default mode to use if none is specified.

In the current release, the only supported `session.type` is `openai_chat`, which uses OpenAI's API or other APIs that provide compatibility, such as with ollama. Lair was originally using langchain and supported various other options which have been removed to simplify the code.

To use Lair with OpenAI, set the environment variable `OPENAI_API_KEY` with your key. The default environment variable to use can be modified with `openai.api_key_environment_variable`.

To use with other OpenAI-compatible APIs, such as ollama, set the configuration variable `openai.api_base`. For example, to use an ollama endpoint: `openai.api_base: http://localhost:11434/v1`.

## Usage

### Lair Core

The following flags are supported when using the `lair` command. They must be provided before the sub-command.

```
  -h, --help               show this help message and exit
  --debug, -d              Enable debugging output
  --disable-color, -c      Do not use color escape sequences
  --force-color, -C        Use color escape sequences, even in pipes
  -M MODE, --mode MODE     Name of the predefined mode to use
  -m MODEL, --model MODEL  Name of the model to use
  -s SET, --set SET        Set a configuration value (-s key=value)
  --version               Display the current version and exit
```

The `--mode` / `-M` flag allows changing the mode (and with it any configuration at startup.)

Individual settings may be overridden with the `--set` / `-s` flag. For example `lair -s 'style.error=bold red' -s ui.multline_input=true chat`.

The `--model` / `-m` flag is a shorthand for setting `model.name`.

### Chat - Command Line Chat Interface

The `chat` command provides a rich command-line interface for interacting with large language models.

Much of the interface is customizable through overriding `display.*` settings. See [here](lair/files/settings.yaml) for a full reference for those settings.

The bottom-toolbar by default shows flags like `[lMvW]`. Flags that are enabled show with capital letters and brighter colors. The current flags are:

| Flag | Meaning                    | Shortcut Key |
|------|----------------------------|--------------|
| L    | Multi-line input           | ESC-L        |
| M    | Markdown rendering         | ESC-M        |
| V    | Verbose (currently unused) | ESC-V        |
| W    | Word-wrapping              | ESC-W        |

#### Commands

| Command          | Description                                                                                               |
|------------------|-----------------------------------------------------------------------------------------------------------|
| /clear           | Clear the conversation history                                                                            |
| /debug           | Toggle debugging                                                                                          |
| /help            | Show available commands and shortcuts                                                                     |
| /history         | Show current conversation                                                                                 |
| /last-prompt     | Display the most recently used prompt                                                                     |
| /last-response   | Display the most recently seen response                                                                   |
| /load            | Load a session from a file  (usage: `/load [filename?]`, default filename is `chat_session.json`)         |
| /mode            | Show or select a mode  (usage: `/mode [name?]`)                                                           |
| /model           | Show or set a model  (usage: `/model [name?]`)                                                            |
| /prompt          | Show or set the system prompt  (usage: `/prompt [prompt?]`)                                               |
| /reload-settings | Reload settings from disk  (resets everything, except current mode)                                       |
| /save            | Save the current session to a file  (usage: `/save [filename?]`, default filename is `chat_session.json`) |
| /set             | Show configuration or set a configuration value for the current mode  (usage: `/set ([key?] [value?])?`)  |

#### Shortcut Keys

In addition to all the standard GNU-readline style key combinations, the following shortcuts are provided.

| Shortcut Key | Action                                    |
|--------------|-------------------------------------------|
| ESC-L        | Toggle multi-line input                   |
| ESC-M        | Toggle markdown rendering                 |
| ESC-T        | Toggle bottom toolbar                     |
| ESC-V        | Toggle verbose output  (currently unused) |
| ESC-W        | Toggle word wrapping                      |

The verbose output options might be removed in the future. They were originally around langchain's verbose flag, but since langchain is no longer used by Lair, their may not be much or any impact from enabling it.

#### Examples

##### Attaching images

Images can be attached by enclosing file names within angle brackets, such as `<foo.png>`. Wildcards (globbing) and `~` for the home directory are also supported, e.g., `<~/images/*.png>`. Note that attaching images to models that do not support visual inputs may lead to unpredictable behavior and some models only work with a single image at a time.

In the following example, an image of two alpacas at a birthday party is provided:

```
crocodile> In just a few words, describe what these alpacas are up to. <~/alpaca.png>
Alpaca birthday party with cupcakes.
```

By default, filenames are not provided, but that behavior can be changed via `model.provide_attachment_filenames`.

```
# Enable providing filenames
crocodile> /set model.provide_attachment_filenames true

# Include all files matching ~/test/*.png
crocodile> Provide an accurate oneliner description for each of the provided images. Max 60 characters. output format: {filename}: {description} <~/test/*.png>
Let's take a look at the images. Here are the descriptions:

burrito.png: A colorful, cartoon-style burrito with cheese and vegetables.
comic.png: A cartoon character with a speech bubble saying "Boom!" in yellow text over a blue background.
electron_microscopy.png: An abstract image of a cell membrane with molecules and membranes visible under an electron microscope.
fantasy_art.png: A fantastical drawing of a dragon breathing fire, surrounded by clouds and lightning bolts.
fractal_thanksgiving.png: An artwork of a turkey's feathers made from mathematical fractals for Thanksgiving celebration.
stained_glass.png: A geometric stained glass window with shapes in red, blue green and yellow that resembles stained leadlight art.
```

These descriptions are really bad. This was using `llama3.2-vision:11b`, which gets confused by multiple images. Providing the filenames also is influencing the answers. For this particular request, it would be better to provide one file per request and not include filenames. See the "Attaching Files" section of the "Util" examples below for a different approach.

##### One-off Chat

Lower `session.max_history_length` to `1`, provides only the prompt and the current message with no history. This can be useful in cases where a conversation history is not desirable, or where one-off requests are being sent.


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
#### Model Settings

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
#### Session Management

The `/save` and `/load` commands can be used for session management.

The `/save` command creates a session file, including the current active configuration, chat history, and some other active state, such as the system prompt.

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

The session that can be loaded with the `/load` command:

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

Session files include the full active configuration. If any sensitive values are stored in the settings, they will also be in the session files.

Loaded sessions will restore all the activate settings. If this is undesirable, `/mode` or `/reload-settings` can be used after `/load` to change to different configuration.


### Util

#### Examples

##### Generating Content

The util command can be used to create content very easily. For example, to create some CSV test data:

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

This could also be used to write simple programs. This can be extremely helpful for one off tasks such as converting a Cloudfront logfile to a JSON format. Here is a simpler example of making a tool to show the times in different timezones:

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

##### Providing Input Content

The util command can operate on content, which could be provided a few different ways. The `--content` / `-c` flags allow providing the content as a string on the command line. The `--content-file` / `-C` flags provide the specified file as content. The `--pipe` / `-p` flags read the content from stdin.

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

##### Attaching Images

The `--attach-file` / `-a` flag allows for attaching one or more image files. Multiple images could be provided via either globbing or providing the repeat `--attach-file` arguments. Globbing and homedir expansion (`~`) is performed automatically. Globs might need to be protected to prevent the shell from expanding them.

Here is a simple example, providing an image and asking for a summary.

```bash
$ lair -m llama3.2-vision:11b util \
    -i 'Provide an accurate oneliner description for each of the provided images. Max 60 characters.' \
    --attach-file electron_microscopy.png
A microscopic view of an electron microscope.
```

Multiple images can be provided at once with globs, such as `--atach-file \*.png`. By default, the model is not provided the filenames. In the example below, the `--include-filenames` / `-F` flag is used to enable sending the filenames with each image.

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

Unfortunately, at a lot of models currently get confused when provided multiple images. That should improve in the future, but for now, a safer (and slower) alternative might be to run the command once per image. This also makes the prior example possible without providing the filenames, which definitely impacted the previous response. For example:

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
