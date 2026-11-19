# Architecture

TapHerd is a local Python connector. The CLI and MCP server use the same device registry and actions, so both interfaces apply the same active device limit.

| Package | Responsibility |
| --- | --- |
| `tapherd.devices` | Discover devices through ADB, choose the active set, and track device status. |
| `tapherd.ui` | Capture screenshots and read the Android UI tree. |
| `tapherd.actions` | Send Android input, launch apps, and transfer media. |
| `tapherd.recipes` | Load and validate YAML, run posting steps, and collect recovery screenshots and UI state. |

The registry saves labels, explicit selections, and addresses supplied through `tapherd connect` in a local JSON file. It replaces the file atomically when saving. Each device operation takes a per-serial lock and one of the registry's three operation slots. A shared registry lock keeps explicit selections stable while actions run. The CLI and MCP processes coordinate through the same registry directory.

The MCP server uses FastMCP from the official Python SDK. It serves stdio by default and can serve Streamable HTTP on loopback. It runs synchronous ADB calls in worker threads and returns structured tool results. Screenshots also include a PNG image block. [MCP setup](MCP.md)

TapHerd attempts a targeted reconnect when a requested device is offline and eligible to act. A remote address supplied through `tapherd connect` can also be restored when it disappears. Connection recovery happens before dispatch. Each requested action runs once.

The recipe engine validates and binds parameters before dispatch. Each run uses the device's existing registry lock and concurrency slot through its last step. Results include per-device status and local artifacts for manual recovery. [Recipe authoring](RECIPES.md)

The private cloud service will live in a separate repository. The local connector will use that service through a documented API when explicitly configured.
