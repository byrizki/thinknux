"""Hardware control interfaces for ThinkNux."""

from .battery import (
    get_battery_info,
    get_battery_thresholds,
    get_charge_behaviour,
    set_battery_thresholds,
    set_charge_behaviour,
    threshold_paths,
)
from .fan import (
    FAN_WATCHDOG_SECS,
    PROC_FAN,
    VALID_FAN_SPEEDS,
    get_current_fan_level,
    get_current_fan_speed_rpm,
    get_fan_capability,
    get_fan_status,
    is_valid_speed,
    parse_fan_proc,
    restore_fan_to_auto_blocking,
    set_fan_speed,
)
from .firmware import (
    get_firmware_attribute,
    get_firmware_status,
    has_bios_admin_password,
    is_thinklmi_supported,
    set_firmware_attribute,
)
from .leds import (
    get_available_leds,
    set_led_brightness,
    set_led_trigger,
    set_lid_logo_dot_mode,
)
from .monitor import collect_system_stats
from .performance import (
    PROFILE_RAPL_MAPPING,
    apply_rapl_for_profile,
    get_cpu_info,
    get_power_profile,
    get_turbo_boost_status,
    set_cpu_governor,
    set_power_profile,
    set_turbo_boost,
)
from .rapl import (
    get_rapl_limits,
    is_rapl_supported,
    set_rapl_limits,
)
from .system_info import get_system_info
from .thermal import get_sensor_data
from .trackpoint import (
    find_trackpoint_dir,
    get_trackpoint_config,
    reset_trackpoint_defaults,
    set_trackpoint_press_to_select,
    set_trackpoint_sensitivity,
)

__all__ = [
    "FAN_WATCHDOG_SECS",
    "PROC_FAN",
    "VALID_FAN_SPEEDS",
    "get_fan_capability",
    "get_fan_status",
    "is_valid_speed",
    "parse_fan_proc",
    "restore_fan_to_auto_blocking",
    "set_fan_speed",
    "get_battery_info",
    "get_battery_thresholds",
    "set_battery_thresholds",
    "get_charge_behaviour",
    "set_charge_behaviour",
    "threshold_paths",
    "get_cpu_info",
    "get_power_profile",
    "get_turbo_boost_status",
    "set_cpu_governor",
    "set_power_profile",
    "set_turbo_boost",
    "PROFILE_RAPL_MAPPING",
    "apply_rapl_for_profile",
    "collect_system_stats",
    "get_system_info",
    "get_sensor_data",
    "is_thinklmi_supported",
    "has_bios_admin_password",
    "get_firmware_attribute",
    "get_firmware_status",
    "set_firmware_attribute",
    "find_trackpoint_dir",
    "get_trackpoint_config",
    "set_trackpoint_sensitivity",
    "set_trackpoint_press_to_select",
    "reset_trackpoint_defaults",
    "get_available_leds",
    "set_led_brightness",
    "set_led_trigger",
    "set_lid_logo_dot_mode",
    "is_rapl_supported",
    "get_rapl_limits",
    "set_rapl_limits",
]
