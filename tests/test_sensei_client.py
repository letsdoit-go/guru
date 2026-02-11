"""
Unit tests for sensei_client.py (SenseiClient).

Tests focus on observer event emissions and async gRPC behavior,
with mocked gRPC connections.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call


@pytest.fixture
def mock_observer():
    """Mock the observer module."""
    with patch('glue_app.sensei_client.observer') as mock:
        mock.emit = AsyncMock()
        yield mock


@pytest.fixture
def mock_grpc_aio():
    """Mock the grpc.aio module."""
    with patch('glue_app.sensei_client.grpc.aio') as mock:
        yield mock


@pytest.fixture
def mock_proto_modules():
    """Mock the protobuf modules at module level."""
    mock_pb2 = MagicMock()
    mock_pb2_grpc = MagicMock()

    with patch('glue_app.sensei_client.sensei_rpc_pb2', mock_pb2), \
         patch('glue_app.sensei_client.sensei_rpc_pb2_grpc', mock_pb2_grpc):
        yield mock_pb2, mock_pb2_grpc


@pytest.fixture
def client(mock_observer, mock_grpc_aio, mock_proto_modules):
    """Create a SenseiClient with all dependencies mocked."""
    from glue_app.sensei_client import SenseiClient
    return SenseiClient("localhost:50051")


class TestSenseiClientInitialization:
    """Tests for SenseiClient initialization."""

    def test_initialization_sets_streaming_flag(self, client):
        """Test that streaming flag is initialized correctly."""
        assert client._streaming is False

    def test_initialization_sets_server_address(self, client):
        """Test that server address is set correctly."""
        assert client.server_address == "localhost:50051"


class TestSenseiClientConnection:
    """Tests for connection and disconnection."""

    @pytest.mark.asyncio
    async def test_connect_creates_channel_and_stub(self, mock_grpc_aio, mock_proto_modules, client):
        """Test that connect() creates gRPC channel and stub."""
        mock_pb2, mock_pb2_grpc = mock_proto_modules
        mock_channel = MagicMock()
        mock_stub = MagicMock()
        mock_grpc_aio.insecure_channel.return_value = mock_channel
        mock_pb2_grpc.SenseiControllerStub.return_value = mock_stub

        await client.connect()

        # Verify channel and stub were created
        mock_grpc_aio.insecure_channel.assert_called_once_with("localhost:50051")
        mock_pb2_grpc.SenseiControllerStub.assert_called_once_with(mock_channel)
        assert client.channel == mock_channel
        assert client.stub == mock_stub

    @pytest.mark.asyncio
    async def test_disconnect_sets_flag_and_closes_channel(self, mock_grpc_aio, client):
        """Test that disconnect() sets streaming flag and closes the channel."""
        mock_channel = AsyncMock()
        mock_grpc_aio.insecure_channel.return_value = mock_channel

        await client.connect()
        client._streaming = True

        await client.disconnect()

        # Verify streaming flag was set to False
        assert client._streaming is False
        # Verify channel was closed
        mock_channel.close.assert_called_once()
        assert client.channel is None
        assert client.stub is None


class TestGetControllerMap:
    """Tests for get_controller_map() method."""

    @pytest.mark.asyncio
    async def test_get_controller_map_emits_new_ctrl_map(self, mock_observer, mock_proto_modules, client):
        """Test that get_controller_map() emits NewControllerMap event."""
        mock_pb2, _ = mock_proto_modules

        # Create mock response
        mock_response = MagicMock()
        mock_pot1 = MagicMock()
        mock_pot1.name = "POT1"
        mock_pot1.id = 1
        mock_response.pots = [mock_pot1]
        mock_response.switches = []

        client.stub = AsyncMock()
        client.stub.GetControllerMap.return_value = mock_response

        await client.get_controller_map()

        # Verify observer.emit was called with NewControllerMap
        expected_map = {"POT1": 1}
        mock_observer.emit.assert_awaited_once_with("NewControllerMap", expected_map)

    @pytest.mark.asyncio
    async def test_get_controller_map_with_pots_and_switches(self, mock_observer, mock_proto_modules, client):
        """Test that get_controller_map() handles both pots and switches."""
        mock_pb2, _ = mock_proto_modules

        # Create mock response
        mock_response = MagicMock()
        mock_pot1 = MagicMock()
        mock_pot1.name = "POT1"
        mock_pot1.id = 1
        mock_switch1 = MagicMock()
        mock_switch1.name = "SW1"
        mock_switch1.id = 2
        mock_response.pots = [mock_pot1]
        mock_response.switches = [mock_switch1]

        client.stub = AsyncMock()
        client.stub.GetControllerMap.return_value = mock_response

        await client.get_controller_map()

        # Verify controller map contains both
        expected_map = {"POT1": 1, "SW1": 2}
        mock_observer.emit.assert_awaited_once_with("NewControllerMap", expected_map)

    @pytest.mark.asyncio
    async def test_get_controller_map_raises_if_not_connected(self, client):
        """Test that get_controller_map() raises error if not connected."""
        with pytest.raises(RuntimeError, match="Not connected to server"):
            await client.get_controller_map()


class TestStreamEvents:
    """Tests for the stream_events() method."""

    @pytest.mark.asyncio
    async def test_stream_events_emits_ui_event_for_each_event(self, mock_observer, client):
        """Test that stream_events() emits UiEvent for each received event."""
        # Create mock events
        mock_event1 = MagicMock()
        mock_event2 = MagicMock()
        mock_event3 = MagicMock()

        client.stub = MagicMock()
        client._streaming = True  # Enable streaming

        # Mock subscribe_to_events to return async generator
        async def event_generator():
            yield mock_event1
            yield mock_event2
            yield mock_event3
            client._streaming = False  # Stop after 3 events

        with patch.object(client, 'subscribe_to_events', return_value=event_generator()):
            await client.stream_events()

        # Verify observer.emit was called for each event
        expected_calls = [
            call("UiEvent", mock_event1),
            call("UiEvent", mock_event2),
            call("UiEvent", mock_event3),
        ]
        mock_observer.emit.assert_has_awaits(expected_calls)
        assert mock_observer.emit.await_count == 3

    @pytest.mark.asyncio
    async def test_stream_events_stops_when_streaming_flag_is_false(self, mock_observer, client):
        """Test that stream_events() respects the _streaming flag."""
        client.stub = MagicMock()
        client._streaming = False  # Already stopped

        # Mock subscribe_to_events with infinite generator
        async def infinite_events():
            while True:
                yield MagicMock()

        with patch.object(client, 'subscribe_to_events', return_value=infinite_events()):
            await client.stream_events()

        # Should not have emitted any events since _streaming was False
        mock_observer.emit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stream_events_handles_grpc_error(self, client):
        """Test that stream_events() handles gRPC errors gracefully."""
        client.stub = MagicMock()
        client._streaming = True

        # Create mock grpc.aio.AioRpcError
        from grpc import StatusCode

        class FakeAioRpcError(Exception):
            pass

        with patch('glue_app.sensei_client.grpc.aio.AioRpcError', FakeAioRpcError):
            grpc_error = FakeAioRpcError("gRPC error")
            with patch.object(client, 'subscribe_to_events', side_effect=grpc_error):
                # Should not raise, just log
                await client.stream_events()

        # Stream should have completed without crashing (no assertion needed)

    @pytest.mark.asyncio
    async def test_stream_events_handles_general_exception(self, client):
        """Test that stream_events() handles general exceptions gracefully."""
        client.stub = MagicMock()
        client._streaming = True

        # Mock subscribe_to_events to raise generic exception
        with patch.object(client, 'subscribe_to_events', side_effect=RuntimeError("Test error")):
            # Should not raise, just log
            await client.stream_events()

        # Stream should have completed without crashing (no assertion needed)


class TestSubscribeToEvents:
    """Tests for the subscribe_to_events() method."""

    @pytest.mark.asyncio
    async def test_subscribe_to_events_with_no_controller_ids(self, mock_proto_modules, client):
        """Test that subscribe_to_events() subscribes to all controllers when no IDs provided."""
        mock_pb2, _ = mock_proto_modules
        mock_request = MagicMock()
        mock_pb2.SubscribeRequest.return_value = mock_request

        mock_event1 = MagicMock()
        mock_event2 = MagicMock()

        # Create async iterator mock
        async def mock_stream():
            yield mock_event1
            yield mock_event2

        client.stub = MagicMock()
        client.stub.SubscribeToEvents.return_value = mock_stream()

        # Subscribe with no controller_ids
        events = []
        async for event in client.subscribe_to_events():
            events.append(event)

        # Verify request was created with empty controller_ids
        mock_pb2.SubscribeRequest.assert_called_once()
        mock_request.controller_ids.extend.assert_not_called()

        # Verify we got the events
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_subscribe_to_events_with_controller_ids(self, mock_proto_modules, client):
        """Test that subscribe_to_events() filters by controller IDs when provided."""
        mock_pb2, _ = mock_proto_modules
        mock_request = MagicMock()
        mock_pb2.SubscribeRequest.return_value = mock_request

        mock_event = MagicMock()

        # Create async iterator mock
        async def mock_stream():
            yield mock_event

        client.stub = MagicMock()
        client.stub.SubscribeToEvents.return_value = mock_stream()

        # Subscribe with specific controller_ids
        controller_ids = [1, 2, 3]
        events = []
        async for event in client.subscribe_to_events(controller_ids):
            events.append(event)

        # Verify request was created with controller_ids
        mock_request.controller_ids.extend.assert_called_once_with([1, 2, 3])

        # Verify we got the events
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_subscribe_to_events_raises_if_not_connected(self, client):
        """Test that subscribe_to_events() raises error if not connected."""
        with pytest.raises(RuntimeError, match="Not connected to server"):
            async for event in client.subscribe_to_events():
                pass


class TestUpdateLed:
    """Tests for the _update_led() method."""

    @pytest.mark.asyncio
    async def test_update_led_sends_request(self, mock_proto_modules, client):
        """Test that _update_led() sends the correct request."""
        mock_pb2, _ = mock_proto_modules
        mock_request = MagicMock()
        mock_pb2.UpdateLedRequest.return_value = mock_request

        client.stub = AsyncMock()

        await client._update_led(led_id=5, active=True)

        # Verify request was created and sent
        mock_pb2.UpdateLedRequest.assert_called_once_with(controller_id=5, active=True)
        client.stub.UpdateLed.assert_awaited_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_update_led_raises_if_not_connected(self, client):
        """Test that _update_led() raises error if not connected."""
        with pytest.raises(RuntimeError, match="Not connected to server"):
            await client._update_led(led_id=1, active=True)


class TestPrintToMockDisplay:
    """Tests for the _print_to_mock_display() method."""

    @pytest.mark.asyncio
    async def test_print_to_mock_display_sends_request(self, mock_proto_modules, client):
        """Test that _print_to_mock_display() sends the correct request."""
        mock_pb2, _ = mock_proto_modules
        mock_request = MagicMock()
        mock_pb2.WriteToDisplayRequest.return_value = mock_request

        client.stub = AsyncMock()

        await client._print_to_mock_display("Hello")

        # Verify request was created and sent
        mock_pb2.WriteToDisplayRequest.assert_called_once_with(data="Hello")
        client.stub.WriteToDisplay.assert_awaited_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_print_to_mock_display_raises_if_not_connected(self, client):
        """Test that _print_to_mock_display() raises error if not connected."""
        with pytest.raises(RuntimeError, match="Not connected to server"):
            await client._print_to_mock_display("Test")
