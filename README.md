# Guru

An asyncio-based Python package for building event-driven bridge applications that connect hardware controllers (pedals, pots, switches) to the Sushi audio engine. Built on Python's native asyncio, guru uses async/await throughout with an internal event system for decoupled communication between all components.

## Architecture

### Asyncio Design

Guru is built entirely on Python's asyncio:

- **Async/await throughout**: All I/O operations use async/await for efficient concurrent execution
- **TaskGroup management**: Uses `asyncio.TaskGroup` to manage concurrent tasks with proper error handling
- **Async gRPC**: Both Sensei and Sushi clients use `grpc.aio` for non-blocking gRPC communication
- **Async observer**: The event system supports both synchronous and asynchronous callbacks
- **Graceful shutdown**: Signal handlers integrated with asyncio for clean shutdown

### Event-Driven Design

All communication between managers happens through an internal pub/sub event system (`observer.py`). Components emit events and subscribe to events without direct dependencies on each other:

```
Hardware → Sensei Client → [UiEvent] → Mapping Manager → [SushiEvent] → Sushi Client → Audio Engine
                ↓                          ↓                  ↓
            [NewControllerMap]          [InitMapping]    [MappingsInitialized]
```

### Core Managers

#### 1. SenseiClient (sensei_client.py)
**Hardware Interface Manager**

Sensei is the abstraction that interfaces with hardware controllers. It has a gRPC backend to emit events
for controller updates.

SenseiClient connects to the Sensei gRPC server and streams hardware controller events asynchronously.

**Responsibilities:**
- Establishes async gRPC connection to Sensei server using `grpc.aio`
- Discovers available hardware controllers via `GetControllerMap()`
- Streams hardware events asynchronously in background task
- Controls LEDs on the board
- [dev workflow] Prints to the mock display

**Events Emitted:**
- `UiEvent` - Hardware controller events (analog, toggle, relative, range)
  - Emitted continuously from async stream as hardware events occur
  - Payload: `sensei_rpc_pb2.Event` (contains controller_id, timestamp, value)
- `NewControllerMap` - Controller discovery results
  - Emitted once after `get_controller_map()` completes
  - Payload: `dict[str, int]` mapping controller names to IDs

**Events Subscribed:**
- `PrintToMockDisplay` -
- `ToggleLedRequest`

#### 2. MappingManager (mappings.py)
**Event Routing Manager**

Central hub that routes hardware events to Sushi parameters based on user-defined mappings.

**Responsibilities:**
- Maintains mappings between controller IDs and Sushi parameters
- Processes incoming hardware events and applies transformations (preprocessors)
- Routes events to appropriate Sushi targets (plugins or tracks)
- Handles different event types (analog, toggle, relative, range)

**Events Subscribed:**
- `UiEvent` - Processes hardware events and routes to Sushi
- `NewControllerMap` - Updates internal controller name→ID mapping
- `MappingsInitialized` - Confirms Sushi initialization completed

**Events Emitted:**
- `InitMapping` - Requests Sushi to initialize mappings
  - Emitted during startup after controller discovery
  - Payload: `list[PluginParameterMapping]` to be initialized
- `SushiPluginEvent` - Requests plugin parameter change
  - Emitted when hardware events map to plugin parameters
  - Payload: `dict` with `track_id`, `plugin_id`, `param_id`, `value`
- `SushiTrackEvent` - Requests track parameter change
  - Emitted when hardware events map to track parameters
  - Payload: `dict` with `track_id`, `param_id`, `value`

#### 3. SushiClient (sushi_client.py)
**Audio Engine Interface Manager**

Wraps elkpy's SushiController and manages communication with the Sushi audio engine.

**Responsibilities:**
- Establishes connection to Sushi gRPC server (elkpy uses sync gRPC)
- Initializes mappings by resolving string names to numeric IDs
- Executes parameter changes in Sushi via elkpy
- [Optional] subscribes to parameter updates from Sushi

**Events Subscribed:**
- `InitMapping` - Initializes all mappings with Sushi
- `SushiPluginEvent` - Sets plugin parameter values
- `SushiTrackEvent` - Sets track parameter values

**Events Emitted:**
- `MappingsInitialized` - Signals successful mapping initialization
  - Emitted after all mappings resolve their IDs
  - Payload: None
- `SushiParameterUpdate` - (only if subscribed to Sushi's notifications)
  - Emitted when Sushi notifies of a parameter update

## Event Flow Examples

### Startup Sequence
```
1. GlueApp.initialize() called
   → SenseiClient.connect() establishes async gRPC channel
   → SenseiClient.get_controller_map() fetches controllers

2. SenseiClient.get_controller_map()
   → emits NewControllerMap
   → MappingManager receives controller map

3. MappingManager.initialize_mappings()
   → emits InitMapping
   → SushiClient resolves track/plugin/parameter names to IDs

4. SushiClient completes initialization
   → emits MappingsInitialized
   → MappingManager confirms ready state

5. GlueApp.run() starts TaskGroup
   → SenseiClient.stream_events() task starts
   → Event processing begins
```

### Runtime Event Processing
```
1. Hardware pot turned
   → Sensei sends gRPC event
   → SenseiClient receives in async stream
   → emits UiEvent (AnalogEvent, controller_id=5, value=0.75)

2. MappingManager receives UiEvent
   → Looks up mapping for controller_id=5
   → Applies preprocessor (e.g., scaling)
   → emits SushiPluginEvent (track_id=2, plugin_id=3, param_id=1, value=75.0)

3. SushiClient receives SushiPluginEvent
   → Calls elkpy: set_parameter_value(plugin_id=3, param_id=1, value=75.0)
   → Sushi audio engine updates parameter in real-time
```

## Event Reference

| Event Name | Emitter | Subscribers | Payload | Purpose |
|------------|---------|-------------|---------|---------|
| `UiEvent` | SenseiClient | MappingManager | `sensei_rpc_pb2.Event` | Hardware controller event stream |
| `NewControllerMap` | SenseiClient | MappingManager | `dict[str, int]` | Controller name→ID mapping |
| `InitMapping` | MappingManager | SushiClient | `list[PluginParameterMapping]` | Request mapping initialization |
| `MappingsInitialized` | SushiClient | MappingManager | None | Confirm initialization complete |
| `SushiPluginEvent` | MappingManager | SushiClient | `dict` (track_id, plugin_id, param_id, value) | Request plugin parameter change |
| `SushiTrackEvent` | MappingManager | SushiClient | `dict` (track_id, param_id, value) | Request track parameter change |

---

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Install dependencies
uv sync

# Install development dependencies (for testing)
uv sync --extra dev
```

The gRPC code is automatically compiled from `sensei_rpc.proto` during package build.

## Configuration

### 1. Server Addresses

Configure connection addresses when creating your `GlueApp` instance:

```python
from guru.app import GlueApp

app = GlueApp(
    mappings=MAPPINGS,
    sensei_address="localhost:50051",  # Sensei gRPC server
    sushi_address="localhost:51051",   # Sushi gRPC server
    log_level=logging.INFO
)
```

### 2. Controller Mappings

Create your mappings using the mapping classes from `guru.mappings`:

```python
from guru.mappings import PluginParameterMapping, TrackParameterMapping, SwitchMapping, ComboMapping

MAPPINGS = [
    # Map a pot to a plugin parameter
    PluginParameterMapping(
        track_name="guitar",
        plugin_name="distortion",
        parameter_name="gain",
        controller_name="POT1",
        preprocessor=lambda x: 0.4 + x * 0.6  # Linear interpolation
    ),

    # Map a pot directly to a track parameter
    TrackParameterMapping(
        track_name="main",
        parameter_name="gain",
        controller_name="POT2",
    ),

    # Map a switch to start playing a wave file
    SwitchMapping(
        track_name="guitar",
        plugin_name="wav_streamer",
        parameter_name="playing",
        controller_name="SW1",
        pressed_value=1.0,
        released_value=0.0
    ),

    # Map a switch to bypass 2 plugins
    ComboMapping(
        controller_name="SW2",
        mappings=[
            BypassMapping(
                plugin_name="reverb",
            ),
            BypassMapping(
                plugin_name="distortion",
            )
        ]
    )
]
```

Be aware that track, plugin and parameter names *MUST* match their counterparts in Sushi's configuration file.
Similarly, controller names *MUST* match theirs in Sensei's configuration.

**NOTE**: If you do not have access to Sensei configuration file (`sensei_config.json`), you can get it from
a running Sensei with:

```python
import asyncio
from guru.sensei_client import SenseiClient

async def main():
    client = SenseiClient()
    await client.connect()
    controller_map = await client.get_controller_map()
    print(controller_map)

asyncio.run(main())
```

Preprocessors are straight-forward Python lambdas. They default to None.

#### Combo mappings
`ComboMapping` is an easy way to assign several mappings to the same controller. Actually it is the only way!


## Usage

### Basic Usage

```python
import asyncio
import logging
from guru.app import GlueApp
from your_mappings import MAPPINGS

async def main():
    # Create the app
    app = GlueApp(
        mappings=MAPPINGS,
        sensei_address="localhost:50051",
        sushi_address="localhost:51051",
        log_level=logging.INFO
    )

    # Initialize connections
    if not await app.initialize():
        return 1

    # Run the event loop
    return await app.run()

if __name__ == "__main__":
    exit(asyncio.run(main()))
```

The application will:
1. Initialize SenseiClient and connect to hardware interface
2. Discover available controllers (`NewControllerMap` event)
3. Initialize SushiClient and connect to audio engine
4. Initialize all mappings (`InitMapping` → `MappingsInitialized` events)
5. Start async task group with event streaming task
6. Process events in real-time through the event system

Press `Ctrl+C` to stop gracefully.

### Advanced Usage: Emitting Events

You can emit events to the system from your code:

```python
import asyncio
from guru.app import GlueApp
from guru import observer
from your_mappings import MAPPINGS

async def main():
    app = GlueApp(mappings=MAPPINGS, log_level=logging.DEBUG)

    # Initialize first
    await app.initialize()

    # Now you can emit events
    await observer.emit("PrintToMockDisplay", "Hello NAMM!")

    # Start the event loop
    return await app.run()

if __name__ == "__main__":
    exit(asyncio.run(main()))
```

## Hardware Event Types

The Sensei server can emit four types of hardware events, all delivered via the `UiEvent`:

### AnalogEvent
Continuous value from pots, faders, expression pedals.
- **Fields:** `controller_id`, `timestamp`, `value` (float 0-1)
- **Usage:** Direct parameter control with optional preprocessing

### ToggleEvent
Binary state from switches, buttons, footswitches.
- **Fields:** `controller_id`, `timestamp`, `value` (bool)
- **Usage:** Maps to `pressed_value`/`released_value` in SwitchMapping

### RelativeEvent
Delta values from rotary encoders.
- **Fields:** `controller_id`, `timestamp`, `value` (int delta)
- **Status:** ⚠️ Not fully implemented (logs warning)

### RangeEvent
Discrete positions from rotary switches, multi-position switches.
- **Fields:** `controller_id`, `timestamp`, `value` (int position)
- **Usage:** Converts to float and applies preprocessing

## Development

### Running Tests

```bash
# Run all tests
uv run --extra dev pytest

# Run with coverage
uv run --extra dev pytest --cov

# Run specific test file
uv run --extra dev pytest tests/test_sensei_client.py
```

### Regenerating gRPC Code

After modifying `sensei_rpc.proto`:

```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. --pyi_out=. src/guru/sensei-grpc-api/sensei_rpc.proto
```

### Logging

Adjust `log_level` when creating the `GlueApp`:
- `logging.DEBUG` - Verbose output including all events and observer activity
- `logging.INFO` - Normal operation logs (default)
- `logging.WARNING` - Only warnings and errors

---

## Extending the System

### Adding New Event Types

The event-driven architecture makes it easy to add new features:

1. **Define the event** - Choose a descriptive name (e.g., `LED_UPDATE`)
2. **Emit the event** - Call `await observer.emit("LED_UPDATE", led_id=1, state=True)` from any manager
3. **Subscribe to the event** - Call `observer.subscribe("LED_UPDATE", callback_function)` in any manager
4. **Implement the callback** - Process the event in the subscriber (can be sync or async)

Example: Adding LED feedback support:

```python
# In MappingManager - emit LED updates
await observer.emit("LED_UPDATE", led_id=controller_id, active=True)

# In SenseiClient - subscribe and forward to hardware
observer.subscribe("LED_UPDATE", self._handle_led_update)

async def _handle_led_update(self, led_id: int, active: bool):
    await self.update_led(led_id, active)
```

### Benefits of Event-Driven Design

- **Decoupling:** Managers don't depend on each other's APIs
- **Testability:** Easy to mock events in unit tests
- **Extensibility:** Add new features without modifying existing code
- **Async-friendly:** Events naturally work with asyncio
- **Debugging:** All communication flows through observable event system

## Troubleshooting

### "Controller 'POT1' not found"
- The controller name in your mapping doesn't match hardware
- Check logs for `NewControllerMap` event showing available controllers
- Verify Sensei server is running and controllers are connected

### "Failed to initialize mapping"
- Track, plugin, or parameter name doesn't exist in Sushi
- Review `InitMapping` event in logs showing which mapping failed
- Verify Sushi is running and accessible

### Events not processing
- Check that MappingManager subscribed to `UiEvent` (logged at startup)
- Verify `MappingsInitialized` event was emitted
- Enable `DEBUG` logging to see event flow through observer

### Asyncio-related issues
- Make sure you're using `asyncio.run(main())` to start the app
- All callbacks in the observer can be either sync or async
- Use `await` when calling async methods like `app.initialize()` and `app.run()`

## Project Structure

```
guru/
├── example.py               # Example usage with asyncio.run()
├── example_mappings.py      # Example mapping configurations
├── src/guru/                # Main package
│   ├── __init__.py
│   ├── app.py              # GlueApp - Application orchestrator with asyncio
│   ├── observer.py         # Async pub/sub event system
│   ├── sensei_client.py    # Async Sensei gRPC client
│   ├── sushi_client.py     # SushiClient - audio engine interface
│   ├── mappings.py         # MappingManager + mapping classes
│   ├── presets.py          # Preset management
│   ├── display_manager.py  # Display management utilities
│   ├── sensei_rpc_pb2*.py  # Generated protobuf code
│   └── sensei-grpc-api/    # gRPC API definitions
├── tests/                  # Unit tests
├── pyproject.toml          # Project dependencies and metadata
└── setup.py                # Build configuration
```

## License

GNU Affero General Public License v3.0
