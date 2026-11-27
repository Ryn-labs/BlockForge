# Build modes

BlockForge can make a build in two ways.

- **Step by step** (default): the AI builds one part at a time, looks at the result, runs the checks, and fixes problems before saving. Slower, but the builds come out cleaner.
- **Script**: the AI writes one script for the whole build. Faster and cheaper.

## Setting

Settings -> AI -> Build mode. Stored as `build_mode` in settings.json with the values `step_by_step` (default) and `script`. The old value `loop` is still read and means `step_by_step`.

## When step by step applies

Only for a new build with the AI set to "My Claude account (Claude Code)" and Claude Code installed. These cases use the script mode automatically, and the build log says why:

- edits of an existing build
- the Anthropic API key option
- other AIs (OpenAI, Gemini, local models and so on)
- Claude Code not installed

Choosing a different AI is a separate setting (`engine`) and is not affected by the build mode.
