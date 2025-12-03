"""
Sushi client wrapper for controlling audio engine parameters via elkpy.
"""

import logging
from . import observer
from elkpy import sushicontroller as sc
from elkpy import sushierrors


logger = logging.getLogger(__name__)


class MappingError(Exception):
    pass


class SushiClient:
    """Wrapper for elkpy SushiController with mapping management."""

    def __init__(self, sushi_address: str = "localhost:51051"):
        """
        Initialize the Sushi client.

        Args:
            sushi_address: Address of the Sushi gRPC server (host:port)
        """
        observer.subscribe("SushiPluginEvent", cb=self._handle_sushi_plugin_event)
        observer.subscribe("SushiTrackEvent", cb=self._handle_sushi_track_event)
        observer.subscribe("PluginBypassEvent", cb=self._handle_plugin_bypass_event)
        observer.subscribe("InitMapping", cb=self._initialize_mappings)
        self.sushi_address = sushi_address
        self.controller = None

    def connect(self) -> bool:
        """Establish connection to Sushi."""
        logger.info(f"Connecting to Sushi at {self.sushi_address}")
        self.controller = sc.SushiController(self.sushi_address)
        version = ""
        while version == "":
            assert self.controller is not None
            try:
                version = self.controller.system.get_sushi_version()
            except Exception:
                logger.info("Sushi unavailable!")
                return False
        logger.info("Connected to Sushi")
        return True

    def disconnect(self) -> None:
        """Close the connection to Sushi."""
        if self.controller:
            logger.info("Disconnecting from Sushi")
            self.controller = None

    def subscribe_to_parameter_updates(self):
        assert self.controller is not None
        self.controller.notifications.subscribe_to_parameter_updates(
            cb=self._handle_param_update_notification
        )

    def _handle_param_update_notification(self, notif) -> None:
        observer.emit("SushiParameterUpdate", notif)

    def _handle_sushi_plugin_event(self, event: dict) -> None:
        if not self.controller:
            raise RuntimeError("Not connected to Sushi. Call connect() first.")

        self.controller.parameters.set_parameter_value(
            event["plugin_id"], event["param_id"], event["value"]
        )
        logger.debug(
            f"Set parameter: track={event['track_id']}, processor={event['plugin_id']}, "
            f"param={event['param_id']}, value={event['value']}"
        )

    def _handle_sushi_track_event(self, event: dict) -> None:
        if not self.controller:
            raise RuntimeError("Not connected to Sushi. Call connect() first.")

        self.controller.parameters.set_parameter_value(
            event["track_id"], event["param_id"], event["value"]
        )
        logger.debug(
            f"Set parameter: track={event['track_id']}, "
            f"param={event['param_id']}, value={event['value']}"
        )

    def _handle_plugin_bypass_event(self, event: dict) -> None:
        if not self.controller:
            raise RuntimeError("Not connected to Sushi. Call connect() first.")

        current_state = self.controller.audio_graph.get_processor_bypass_state(
            event["plugin_id"]
        )
        self.controller.audio_graph.set_processor_bypass_state(
            event["plugin_id"], not current_state
        )

    def _initialize_mappings(self, mappings: list) -> None:
        """
        Initialize all mappings by resolving track/plugin/parameter IDs.

        Args:
            mappings: List of Mapping objects to initialize

        Raises:
            RuntimeError: If not connected to Sushi
            Exception: If any mapping fails to initialize (invalid track/plugin/parameter names)
        """
        if not self.controller:
            raise RuntimeError("Not connected to Sushi. Call connect() first.")

        logger.info(f"Initializing {len(mappings)} mappings")
        for i, mapping in enumerate(mappings):
            try:
                mapping.init(self.controller)
                logger.info(
                    f"Mapping {i + 1}: {mapping.controller_name} -> "
                    f"{getattr(mapping, 'track_name', '')}/{getattr(mapping, 'plugin_name', '-')}/{getattr(mapping, 'parameter_name', 'BYPASS')}"
                )
            except sushierrors.SushiNotFoundError:
                logger.error(
                    f"Failed to initialize mapping {i + 1}: No such target in Sushi! Are your mappings aligned with Sushi's config?"
                )
                raise MappingError("Mapping target not found in Sushi")
            except Exception as e:
                logger.error(f"Failed to initialize mapping {i + 1}: {e}")
                raise MappingError("Initializing mappings failed")
        observer.emit("MappingsInitialized")

        logger.info("All mappings initialized successfully")

    def set_parameter_value(
        self, track_id: int, processor_id: int, parameter_id: int, value: float
    ) -> None:
        """
        Set a parameter value in Sushi.

        Args:
            track_id: ID of the track
            processor_id: ID of the processor/plugin
            parameter_id: ID of the parameter
            value: New parameter value
        """
        if not self.controller:
            raise RuntimeError("Not connected to Sushi. Call connect() first.")

        self.controller.parameters.set_parameter_value(
            processor_id, parameter_id, value
        )
        logger.debug(
            f"Set parameter: track={track_id}, processor={processor_id}, "
            f"param={parameter_id}, value={value}"
        )
