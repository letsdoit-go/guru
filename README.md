# Pedal Glue App

An event-driven bridge application that connects hardware controllers (pedals, pots, switches) to the Sushi audio engine. The application uses an internal event system for decoupled communication between all components.

## Architecture

### Event-Driven Design

All communication between managers happens through an internal pub/sub event system (`observer.py`). Components emit events and subscribe to events without direct dependencies on each other:

```
Hardware → Pin Proxy → [UiEvent] → Mapping Manager → [SushiEvent] → Sushi Client → Audio Engine
                ↓                          ↓                  ↓
            [NewControllerMap]          [InitMapping]    [MappingsInitialized]
```

### Core Managers

#### 1. SenseiClient (sensei_client.py)
**Hardware Interface Manager**

Connects to the Sensei gRPC server and streams hardware controller events.

**Responsibilities:**
- Establishes gRPC connection to Sensei server
- Runs event subscription in a background thread
- Discovers available hardware controllers via `RefreshAllStates()`
- Translates hardware events to internal events

**Events Emitted:**
- `UiEvent` - Hardware controller events (analog, toggle, relative, range)
  - Emitted continuously from background thread as hardware events occur
  - Payload: `pin_events_pb2.Event` (contains controller_id, timestamp, value)
- `NewControllerMap` - Controller discovery results
  - Emitted once after `refresh_all_states()` completes
  - Payload: `dict[str, int]` mapping controller names to IDs

**Events Subscribed:** None

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
1. SenseiClient.refresh_all_states()
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
| `UiEvent` | SenseiClient | MappingManager | `pin_events_pb2.Event` | Hardware controller event stream |
| `NewControllerMap` | SenseiClient | MappingManager | `dict[str, int]` | Controller name→ID mapping |
| `InitMapping` | MappingManager | SushiClient | `list[PluginParameterMapping]` | Request mapping initialization |
| `MappingsInitialized` | SushiClient | MappingManager | None | Confirm initialization complete |
| `SushiPluginEvent` | MappingManager | SushiClient | `dict` (track_id, plugin_id, param_id, value) | Request plugin parameter change |
| `SushiTrackEvent` | MappingManager | SushiClient | `dict` (track_id, param_id, value) | Request track parameter change |

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Install dependencies
uv sync

# Install development dependencies (for testing)
uv sync --extra dev
```

The gRPC code is automatically compiled from `pin_events.proto` at runtime by `SenseiClient`.

## Configuration

### 1. Server Addresses

Edit `main.py` to configure connection addresses:

```python
SENSEI_ADDRESS = "localhost:50051"  # Pin Proxy gRPC server
SUSHI_ADDRESS = "localhost:51051"       # Sushi gRPC server
LOG_LEVEL = logging.INFO
```

### 2. Controller Mappings

Create your mappings in `mappings.py`:

```python
from mappings import PluginParameterMapping, TrackParameterMapping, SwitchMapping

MAPPINGS = [
    # Map a pot to a plugin parameter
    PluginParameterMapping(
        track_name="guitar",
        plugin_name="distortion",
        parameter_name="gain",
        controller_name="POT1",
        preprocessor=lambda x: x * 100  # Scale 0-1 to 0-100
    ),

    # Map a pot directly to a track parameter
    TrackParameterMapping(
        track_name="main",
        parameter_name="gain",
        controller_name="POT2",
    ),

    # Map a switch with specific on/off values
    SwitchMapping(
        track_name="guitar",
        plugin_name="reverb",
        parameter_name="bypass",
        controller_name="SW1",
        pressed_value=1.0,
        released_value=0.0
    ),
]
```

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
uv run pytest

# Run with coverage
uv run pytest --cov

# Run specific test file
uv run pytest test_sensei_client.py
```

### Regenerating gRPC Code

After modifying `pin_events.proto`:

```bash
uv run python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. --pyi_out=. pin_events.proto
```

### Logging

Adjust `LOG_LEVEL` in `main.py`:
- `logging.DEBUG` - Verbose output including all events and observer activity
- `logging.INFO` - Normal operation logs (default)
- `logging.WARNING` - Only warnings and errors

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

# In PinProxyClient - subscribe and forward to hardware
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
├── pin_events.proto         # gRPC service definition
├── pin_events_pb2*.py       # Generated protobuf code (auto-generated)
├── test_*.py                # Unit tests with observer mocking
└── pyproject.toml           # Project dependencies
```

## License

[Add your license here]
