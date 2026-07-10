from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfPower,
)

from .const import DOMAIN, LOGGER
from .coordinator import WallboxBLEDataUpdateCoordinator
from .entity import WallboxBLEEntity

# The charger's BLE status frame (GET_STATUS) carries more than status/current:
#   L1/L2/L3 : per-phase current, reported in 0.1 A units
#   en       : session energy counter, ~10 Wh per unit (-> 0.01 kWh)
# We surface these as sensors so energy/power can be read locally (no cloud).
EN_TO_KWH = 0.01          # 'en' counter unit ~= 10 Wh
CURRENT_SCALE = 0.1       # L1/L2/L3 reported in 0.1 A
NOMINAL_VOLTAGE = 230     # V (line-neutral) for the measured-power estimate


@dataclass(frozen=True, kw_only=True)
class WallboxBLESensorDescription(SensorEntityDescription):
    """Sensor description with a value function reading the coordinator."""

    value_fn: Callable[[WallboxBLEDataUpdateCoordinator], object] | None = None


def _amps(coordinator) -> float:
    d = coordinator.data or {}
    return sum(d.get(k, 0) for k in ("L1", "L2", "L3")) * CURRENT_SCALE


def _status(coordinator):
    return coordinator.status


def _energy(coordinator):
    d = coordinator.data or {}
    return round(d.get("en", 0) * EN_TO_KWH, 2)


def _current(coordinator):
    return round(_amps(coordinator), 1)


def _power(coordinator):
    return round(_amps(coordinator) * NOMINAL_VOLTAGE)


ENTITY_DESCRIPTIONS = (
    WallboxBLESensorDescription(
        key="wallbox_ble",
        name="Status",
        value_fn=_status,
    ),
    WallboxBLESensorDescription(
        key="energy",
        name="Session energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=_energy,
    ),
    WallboxBLESensorDescription(
        key="current",
        name="Charging current (measured)",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=_current,
    ),
    WallboxBLESensorDescription(
        key="power",
        name="Charging power (measured)",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=_power,
    ),
)


async def async_setup_entry(hass, entry, async_add_devices):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_devices(
        WallboxBLESensor(
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class WallboxBLESensor(WallboxBLEEntity, SensorEntity):
    def __init__(
        self,
        coordinator: WallboxBLEDataUpdateCoordinator,
        entity_description: WallboxBLESensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = entity_description
        # Keep the original Status sensor's unique_id = entry_id (unchanged);
        # give the new sensors a distinct suffix so they don't collide.
        if entity_description.key != "wallbox_ble":
            self._attr_unique_id = (
                f"{coordinator.config_entry.entry_id}_{entity_description.key}"
            )

    @property
    def available(self):
        return self.coordinator.available

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.coordinator)
