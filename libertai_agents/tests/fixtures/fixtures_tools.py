from typing import Callable

import pytest


@pytest.fixture()
def fake_get_temperature_tool() -> Callable:
    def get_current_temperature(location: str, unit: str) -> float:
        """
        Get the current temperature at a location.

        Args:
            location: The location to get the temperature for, in the format "City, Country"
            unit: The unit to return the temperature in. (choices: ["celsius", "fahrenheit"])
        Returns:
            The current temperature at the specified location in the specified units, as a float.
        """
        return 22.0  # A real function should probably actually get the temperature!

    return get_current_temperature


@pytest.fixture()
def fake_get_temperature_with_new_union_style_param_tool() -> Callable:
    def get_current_temperature(location: str, unit: str | None) -> float:
        """
        Get the current temperature at a location.

        Args:
            location: The location to get the temperature for, in the format "City, Country"
            unit: The unit to return the temperature in. (choices: ["celsius", "fahrenheit"])
        Returns:
            The current temperature at the specified location in the specified units, as a float.
        """
        return 22.0  # A real function should probably actually get the temperature!

    return get_current_temperature
