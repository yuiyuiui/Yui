# Opening Yui test and benchmark tasks

When the user asks for a new task to execute a Yui-results exercise or Yui
benchmark, create its foreground chat with `model="gpt-6.1-sol"` and
`thinking="high"`. Use the trusted project's Standard speed
(`service_tier="default"`). An explicit user selection overrides these defaults.

Send only `Execute <absolute path to the entry README.md>.` to the new task.
The entry owns worker dispatch, the ten-minute heartbeat and terminal cleanup.
