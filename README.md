# Pedal Glue App

An event-driven bridge application that connects hardware controllers (pedals, pots, switches) to the Sushi audio engine. The application uses an internal event system for decoupled communication between all components.

## Architecture

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

SenseiClient connects to the Sensei gRPC server and streams hardware controller events.

**Responsibilities:**
- Establishes gRPC connection to Sensei server
- Discovers available hardware controllers via `GetControllerMap()`
- Translates hardware events to internal events
- Controls LEDs on the board 
- [dev workflow] Prints to the mock display

**Events Emitted:**
- `UiEvent` - Hardware controller events (analog, toggle, relative, range)
  - Emitted continuously from background thread as hardware events occur
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
- Establishes connection to Sushi gRPC server
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
1. SenseiClient.get_controller_map()
   → emits NewControllerMap
   → MappingManager receives controller map

2. MappingManager.initialize_mappings()
   → emits InitMapping
   → SushiClient resolves track/plugin/parameter names to IDs

3. SushiClient completes initialization
   → emits MappingsInitialized
   → MappingManager confirms ready state
```

### Runtime Event Processing
```
1. Hardware pot turned
   → Sensei sends gRPC event
   → SenseiClient receives in background thread
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

The gRPC code is automatically compiled from `sensei_rpc.proto` at runtime by `SenseiClient`.

## Configuration

### 1. Server Addresses

Edit `main.py` to configure connection addresses:

```python
SENSEI_ADDRESS = "localhost:50051"  # Sensei gRPC server
SUSHI_ADDRESS = "localhost:51051"       # Sushi gRPC server
LOG_LEVEL = logging.INFO
```

### 2. Controller Mappings

Create your mappings in `mappings.py`:

```python
from mappings import PluginParameterMapping, TrackParameterMapping, SwitchMapping, ComboMapping

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
uv run sensei_client.py
```

Preprocessors are straight-forward Python lambdas. They default to None.

#### Combo mappings
`ComboMapping` is an easy way to assign several mappings to the same controller. Actually it is the only way!


## Usage

```bash
# Run the application
uv run python main.py
```

The application will:
1. Initialize SenseiClient and connect to hardware interface
2. Discover available controllers (`NewControllerMap` event)
3. Initialize SushiClient and connect to audio engine
4. Initialize all mappings (`InitMapping` → `MappingsInitialized` events)
5. Start background thread subscribing to hardware events
6. Process events in real-time through the event system

Press `Ctrl+C` to stop gracefully.

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
uv run --extra dev pytest test_sensei_client.py
```

### Regenerating gRPC Code

After modifying `sensei_rpc.proto`:

```bash
uv run python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. --pyi_out=. sensei_rpc.proto
```

### Logging

Adjust `LOG_LEVEL` in `main.py`:
- `logging.DEBUG` - Verbose output including all events and observer activity
- `logging.INFO` - Normal operation logs (default)
- `logging.WARNING` - Only warnings and errors

---

## Extending the System

### Adding New Event Types

The event-driven architecture makes it easy to add new features:

1. **Define the event** - Choose a descriptive name (e.g., `LED_UPDATE`)
2. **Emit the event** - Call `observer.emit("LED_UPDATE", led_id=1, state=True)` from any manager
3. **Subscribe to the event** - Call `observer.subscribe("LED_UPDATE", callback_function)` in any manager
4. **Implement the callback** - Process the event in the subscriber

Example: Adding LED feedback support:

```python
# In MappingManager - emit LED updates
observer.emit("LED_UPDATE", led_id=controller_id, active=True)

# In SenseiClient - subscribe and forward to hardware
observer.subscribe("LED_UPDATE", self._handle_led_update)

def _handle_led_update(self, led_id: int, active: bool):
    self.update_led(led_id, active)
```

### Benefits of Event-Driven Design

- **Decoupling:** Managers don't depend on each other's APIs
- **Testability:** Easy to mock events in unit tests
- **Extensibility:** Add new features without modifying existing code
- **Threading:** Events naturally cross thread boundaries
- **Debugging:** All communication flows through observable event system

## Troubleshooting

### "Controller 'POT1' not found"
- The controller name in your mapping doesn't match hardware
- Check logs for `NewControllerMap` event showing available controllers
- Verify Pin Proxy server is running and controllers are connected

### "Failed to initialize mapping"
- Track, plugin, or parameter name doesn't exist in Sushi
- Review `InitMapping` event in logs showing which mapping failed
- Verify Sushi is running and accessible

### Events not processing
- Check that MappingManager subscribed to `UiEvent` (logged at startup)
- Verify `MappingsInitialized` event was emitted
- Enable `DEBUG` logging to see event flow through observer

## Project Structure

```
pedal-glue-app/
├── main.py                  # Application entry point, orchestrates managers
├── observer.py              # Pub/sub event system (subscribe, emit)
├── sensei_client.py         # PinProxyClient - hardware interface manager
├── sushi_client.py          # SushiClient - audio engine interface manager
├── mappings.py              # MappingManager + user configuration
├── presets.py               # Mapping class definitions
├── dispatcher.py            # (Legacy) Original non-event-based dispatcher
├── sensei_rpc.proto         # gRPC service definition
├── sensei_rpc_pb2*.py       # Generated protobuf code (auto-generated)
├── test_*.py                # Unit tests with observer mocking
└── pyproject.toml           # Project dependencies
```

## License

[Add your license here]
