from typing import Callable

import pytest


@pytest.fixture()
def basic_function_for_tool() -> Callable:
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
