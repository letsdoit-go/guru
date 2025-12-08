"""
Unit tests for sensei_client.py (SenseiClient).

Tests focus on observer event emissions and threading behavior,
with mocked gRPC connections.
"""

import pytest
from unittest.mock import MagicMock, Mock, patch, call
import threading
import time


@pytest.fixture
def mock_observer():
    """Mock the observer module."""
    with patch('glue_app.sensei_client.observer') as mock:
        yield mock


@pytest.fixture
def mock_grpc():
    """Mock the grpc module."""
    with patch('glue_app.sensei_client.grpc') as mock:
        yield mock


@pytest.fixture
def mock_proto_modules():
    """Mock the protobuf modules at module level."""
    mock_pb2 = MagicMock()
    mock_pb2_grpc = MagicMock()

    with patch('glue_app.sensei_client.pin_events_pb2', mock_pb2), \
         patch('glue_app.sensei_client.pin_events_pb2_grpc', mock_pb2_grpc):
        yield mock_pb2, mock_pb2_grpc


@pytest.fixture
def client(mock_observer, mock_grpc, mock_proto_modules):
    """Create a SenseiClient with all dependencies mocked."""
    from glue_app.sensei_client import SenseiClient
    return SenseiClient("localhost:50051")


class TestPinProxyClientInitialization:
    """Tests for SenseiClient initialization."""

    def test_initialization_sets_threading_attributes(self, client):
        """Test that threading attributes are initialized correctly."""
        assert client._event_thread is None
        assert client._running is False

    def test_initialization_sets_server_address(self, client):
        """Test that server address is set correctly."""
        assert client.server_address == "localhost:50051"


class TestPinProxyClientConnection:
    """Tests for connection and disconnection."""

    def test_connect_creates_channel_and_stub(self, mock_grpc, mock_proto_modules, client):
        """Test that connect() creates gRPC channel and stub."""
        mock_pb2, mock_pb2_grpc = mock_proto_modules
        mock_channel = MagicMock()
        mock_stub = MagicMock()
        mock_grpc.insecure_channel.return_value = mock_channel
        mock_pb2_grpc.PinProxyServiceStub.return_value = mock_stub

        client.connect()

        # Verify channel and stub were created
        mock_grpc.insecure_channel.assert_called_once_with("localhost:50051")
        mock_pb2_grpc.PinProxyServiceStub.assert_called_once_with(mock_channel)
        assert client.channel == mock_channel
        assert client.stub == mock_stub

    def test_disconnect_stops_thread_and_closes_channel(self, mock_grpc, client):
        """Test that disconnect() stops the event thread and closes the channel."""
        mock_channel = MagicMock()
        mock_grpc.insecure_channel.return_value = mock_channel

        client.connect()
        client._running = True  # Simulate running thread
        client._event_thread = MagicMock()
        client._event_thread.is_alive.return_value = False

        client.disconnect()

        # Verify stop was called (flag set to False)
        assert client._running is False
        # Verify channel was closed
        mock_channel.close.assert_called_once()
        assert client.channel is None
        assert client.stub is None


class TestRefreshAllStates:
    """Tests for refresh_all_states() method."""

    def test_refresh_all_states_emits_new_ctrl_map(self, mock_observer, mock_proto_modules, client):
        """Test that refresh_all_states() emits NewControllerMap event."""
        mock_pb2, _ = mock_proto_modules

        # Create mock response
        mock_response = MagicMock()
        mock_pot1 = MagicMock()
        mock_pot1.name = "POT1"  # Set as attribute, not in constructor
        mock_pot1.id = 1
        mock_pot1.normalized_value = 0.5
        mock_response.pots = [mock_pot1]
        mock_response.switches = []

        mock_request = MagicMock()
        mock_pb2.RefreshAllStatesRequest.return_value = mock_request

        client.stub = MagicMock()
        client.stub.RefreshAllStates.return_value = mock_response

        client.refresh_all_states()

        # Verify observer.emit was called with NewControllerMap
        expected_map = {"POT1": 1}
        mock_observer.emit.assert_called_once_with("NewControllerMap", expected_map)

    def test_refresh_all_states_with_pots_and_switches(self, mock_observer, mock_proto_modules, client):
        """Test that refresh_all_states() handles both pots and switches."""
        mock_pb2, _ = mock_proto_modules

        # Create mock response
        mock_response = MagicMock()
        mock_pot1 = MagicMock()
        mock_pot1.name = "POT1"  # Set as attribute, not in constructor
        mock_pot1.id = 1
        mock_pot1.normalized_value = 0.5
        mock_switch1 = MagicMock()
        mock_switch1.name = "SW1"  # Set as attribute, not in constructor
        mock_switch1.id = 2
        mock_switch1.active = True
        mock_response.pots = [mock_pot1]
        mock_response.switches = [mock_switch1]

        mock_request = MagicMock()
        mock_pb2.RefreshAllStatesRequest.return_value = mock_request

        client.stub = MagicMock()
        client.stub.RefreshAllStates.return_value = mock_response

        client.refresh_all_states()

        # Verify controller map contains both
        expected_map = {"POT1": 1, "SW1": 2}
        mock_observer.emit.assert_called_once_with("NewControllerMap", expected_map)

    def test_refresh_all_states_raises_if_not_connected(self, client):
        """Test that refresh_all_states() raises error if not connected."""
        with pytest.raises(RuntimeError, match="Not connected to server"):
            client.refresh_all_states()


class TestThreadLifecycle:
    """Tests for thread lifecycle management (start/stop)."""

    def test_start_creates_and_starts_thread(self, client):
        """Test that start() creates and starts the event subscription thread."""
        client.stub = MagicMock()

        # Mock subscribe_to_events to prevent actual subscription
        with patch.object(client, 'subscribe_to_events', return_value=iter([])):
            client.start()

            # Verify thread was created and started
            assert client._running is True
            assert client._event_thread is not None
            assert isinstance(client._event_thread, threading.Thread)
            assert client._event_thread.daemon is True

            # Clean up
            client.stop()

    def test_start_does_not_start_if_already_running(self, client):
        """Test that start() does nothing if thread is already running."""
        client.stub = MagicMock()

        # Start once
        with patch.object(client, 'subscribe_to_events', return_value=iter([])):
            client.start()
            first_thread = client._event_thread

            # Try to start again (while still running)
            # The thread should still be considered "alive" for this test
            client.start()

            # Thread won't be the same because first one completed, but _running stays True
            # The key is that start() logged a warning (we can't easily assert that)
            assert client._running is True

            # Clean up
            client.stop()

    def test_stop_sets_running_flag_and_joins_thread(self, client):
        """Test that stop() sets _running to False and waits for thread."""
        client.stub = MagicMock()

        # Start the thread
        with patch.object(client, 'subscribe_to_events', return_value=iter([])):
            client.start()
            time.sleep(0.1)  # Let thread start

            # Stop the thread
            client.stop()

            # Verify flag is False
            assert client._running is False
            # Thread should be None after stopping
            assert client._event_thread is None

    def test_stop_does_nothing_if_not_running(self, client):
        """Test that stop() is safe to call when not running."""
        client._running = False
        client._event_thread = None

        # Should not raise
        client.stop()

        assert client._running is False


class TestEventLoop:
    """Tests for the _event_loop() method."""

    def test_event_loop_emits_ui_event_for_each_event(self, mock_observer, client):
        """Test that _event_loop() emits UiEvent for each received event."""
        # Create mock events
        mock_event1 = MagicMock()
        mock_event2 = MagicMock()
        mock_event3 = MagicMock()

        client.stub = MagicMock()
        client._running = True

        # Mock subscribe_to_events to return test events
        def event_generator():
            yield mock_event1
            yield mock_event2
            yield mock_event3
            client._running = False  # Stop after 3 events

        with patch.object(client, 'subscribe_to_events', return_value=event_generator()):
            client._event_loop()

        # Verify observer.emit was called for each event
        expected_calls = [
            call("UiEvent", mock_event1),
            call("UiEvent", mock_event2),
            call("UiEvent", mock_event3),
        ]
        mock_observer.emit.assert_has_calls(expected_calls)
        assert mock_observer.emit.call_count == 3

    def test_event_loop_stops_when_running_flag_is_false(self, mock_observer, client):
        """Test that _event_loop() respects the _running flag."""
        client.stub = MagicMock()
        client._running = False  # Already stopped

        # Mock subscribe_to_events with infinite generator
        def infinite_events():
            while True:
                yield MagicMock()

        with patch.object(client, 'subscribe_to_events', return_value=infinite_events()):
            client._event_loop()

        # Should not have emitted any events since _running was False
        mock_observer.emit.assert_not_called()

    def test_event_loop_handles_grpc_error(self, mock_grpc, client):
        """Test that _event_loop() handles gRPC errors gracefully."""
        client.stub = MagicMock()
        client._running = True

        # Create a custom exception class that can be caught
        class FakeRpcError(Exception):
            pass

        # Patch grpc.RpcError to be our fake exception class
        mock_grpc.RpcError = FakeRpcError

        grpc_error = FakeRpcError("gRPC error")
        with patch.object(client, 'subscribe_to_events', side_effect=grpc_error):
            # Should not raise, just log
            client._event_loop()

        # Event loop should have completed without crashing (no assertion needed)

    def test_event_loop_handles_general_exception(self, mock_grpc, client):
        """Test that _event_loop() handles general exceptions gracefully."""
        client.stub = MagicMock()
        client._running = True

        # Create a custom exception class for grpc.RpcError so the first except clause doesn't match
        class FakeRpcError(Exception):
            pass

        mock_grpc.RpcError = FakeRpcError

        # Mock subscribe_to_events to raise generic exception
        with patch.object(client, 'subscribe_to_events', side_effect=RuntimeError("Test error")):
            # Should not raise, just log
            client._event_loop()

        # Event loop should have completed without crashing (no assertion needed)


class TestSubscribeToEvents:
    """Tests for the subscribe_to_events() method."""

    def test_subscribe_to_events_with_no_controller_ids(self, mock_proto_modules, client):
        """Test that subscribe_to_events() subscribes to all controllers when no IDs provided."""
        mock_pb2, _ = mock_proto_modules
        mock_request = MagicMock()
        mock_pb2.SubscribeRequest.return_value = mock_request

        mock_event_stream = [MagicMock(), MagicMock()]

        client.stub = MagicMock()
        client.stub.SubscribeToEvents.return_value = iter(mock_event_stream)

        # Subscribe with no controller_ids
        events = list(client.subscribe_to_events())

        # Verify request was created with empty controller_ids
        mock_pb2.SubscribeRequest.assert_called_once()
        mock_request.controller_ids.extend.assert_not_called()

        # Verify we got the events
        assert len(events) == 2

    def test_subscribe_to_events_with_controller_ids(self, mock_proto_modules, client):
        """Test that subscribe_to_events() filters by controller IDs when provided."""
        mock_pb2, _ = mock_proto_modules
        mock_request = MagicMock()
        mock_pb2.SubscribeRequest.return_value = mock_request

        mock_event_stream = [MagicMock()]

        client.stub = MagicMock()
        client.stub.SubscribeToEvents.return_value = iter(mock_event_stream)

        # Subscribe with specific controller_ids
        controller_ids = [1, 2, 3]
        events = list(client.subscribe_to_events(controller_ids))

        # Verify request was created with controller_ids
        mock_request.controller_ids.extend.assert_called_once_with([1, 2, 3])

        # Verify we got the events
        assert len(events) == 1

    def test_subscribe_to_events_raises_if_not_connected(self, client):
        """Test that subscribe_to_events() raises error if not connected."""
        with pytest.raises(RuntimeError, match="Not connected to server"):
            list(client.subscribe_to_events())


class TestUpdateLed:
    """Tests for the update_led() method."""

    def test_update_led_sends_request(self, mock_proto_modules, client):
        """Test that update_led() sends the correct request."""
        mock_pb2, _ = mock_proto_modules
        mock_request = MagicMock()
        mock_pb2.UpdateLedRequest.return_value = mock_request

        client.stub = MagicMock()

        client.update_led(led_id=5, active=True)

        # Verify request was created and sent
        mock_pb2.UpdateLedRequest.assert_called_once_with(led_id=5, active=True)
        client.stub.UpdateLed.assert_called_once_with(mock_request)

    def test_update_led_raises_if_not_connected(self, client):
        """Test that update_led() raises error if not connected."""
        with pytest.raises(RuntimeError, match="Not connected to server"):
            client.update_led(led_id=1, active=True)
