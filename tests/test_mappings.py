import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from guru.mappings import MappingManager, MappingMode, PluginParameterMapping


MAPPINGS=[
MappingMode(
        [
            PluginParameterMapping(
                track_name="TRACK",
                plugin_name="GxVintageFuzzMaster",
                parameter_name="INTENSITY",
                controller_name="ENC1",
                parameter_label="Fuzz",
            )
        ],
        1,
    )
]


@pytest.mark.asyncio
async def test_initialize_mappings():
    with patch("guru.mappings.observer.emit", new_callable=AsyncMock) as mock_emit, \
    patch("guru.mappings.observer.subscribe"):
        mgr = MappingManager()
        await mgr.initialize_mappings(MAPPINGS)
        mock_emit.assert_awaited_with(signal="InitMapping", mappings = MAPPINGS[0].mappings)

