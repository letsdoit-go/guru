"""
gRPC client for connecting to PinProxyService and subscribing to hardware events.
"""

import grpc
import logging
from typing import Iterator, Dict

import pin_events_pb2
import pin_events_pb2_grpc


logger = logging.getLogger(__name__)


class PinProxyClient:
    """Client for connecting to the Pin Proxy gRPC service."""

    def __init__(self, server_address: str = "localhost:50051"):
        """
        Initialize the Pin Proxy client.

        Args:
            server_address: Address of the gRPC server (host:port)
        """
        self.server_address = server_address
        self.channel = None
        self.stub = None

    def connect(self) -> None:
        """Establish connection to the gRPC server."""
        logger.info(f"Connecting to Pin Proxy at {self.server_address}")
        self.channel = grpc.insecure_channel(self.server_address)
        self.stub = pin_events_pb2_grpc.PinProxyServiceStub(self.channel)
        logger.info("Connected to Pin Proxy")

    def disconnect(self) -> None:
        """Close the gRPC connection."""
        if self.channel:
            logger.info("Disconnecting from Pin Proxy")
            self.channel.close()
            self.channel = None
            self.stub = None

    def refresh_all_states(self) -> Dict[str, int]:
        """
        Request current state of all controllers and build name->ID mapping.

        Returns:
            Dictionary mapping controller names to their IDs
        """
        if not self.stub:
            raise RuntimeError("Not connected to server. Call connect() first.")

        logger.info("Requesting controller states via RefreshAllStates()")
        request = pin_events_pb2.RefreshAllStatesRequest()
        response = self.stub.RefreshAllStates(request)

        controller_map = {}

        # Map pot names to IDs
        for pot in response.pots:
            controller_map[pot.name] = pot.id
            logger.debug(f"Pot: {pot.name} -> ID {pot.id} (value: {pot.normalized_value})")

        # Map switch names to IDs
        for switch in response.switches:
            controller_map[switch.name] = switch.id
            logger.debug(f"Switch: {switch.name} -> ID {switch.id} (active: {switch.active})")

        logger.info(f"Discovered {len(controller_map)} controllers")
        return controller_map

    def subscribe_to_events(
        self, controller_ids: list[int] | None = None
    ) -> Iterator[pin_events_pb2.Event]:
        """
        Subscribe to hardware events stream.

        Args:
            controller_ids: Optional list of controller IDs to filter events.
                          If None, subscribe to all controllers.

        Yields:
            Event messages from the server
        """
        if not self.stub:
            raise RuntimeError("Not connected to server. Call connect() first.")

        request = pin_events_pb2.SubscribeRequest()
        if controller_ids:
            request.controller_ids.extend(controller_ids)
            logger.info(f"Subscribing to events for controllers: {controller_ids}")
        else:
            logger.info("Subscribing to all controller events")

        try:
            for event in self.stub.SubscribeToEvents(request):
                yield event
        except grpc.RpcError as e:
            logger.error(f"gRPC error during event subscription: {e}")
            raise

    def update_led(self, led_id: int, active: bool) -> None:
        """
        Update the state of an LED.

        Args:
            led_id: ID of the LED to update
            active: Whether the LED should be on (True) or off (False)
        """
        if not self.stub:
            raise RuntimeError("Not connected to server. Call connect() first.")

        request = pin_events_pb2.UpdateLedRequest(led_id=led_id, active=active)
        self.stub.UpdateLed(request)
        logger.debug(f"Updated LED {led_id} to {'active' if active else 'inactive'}")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
