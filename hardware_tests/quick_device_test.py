"""
Quick hardware test for specific RDM Device APIs.

Simple script to quickly test individual APIs with real hardware.

Usage:
    python quick_device_test.py [--port COM3] [--test sensors]
"""

import argparse
import asyncio
import logging

from rdm_dmx_async import NetworkConfig, NetworkManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def test_basic_info(device):
    """Test basic device information."""
    print("\n=== Basic Device Information ===")

    # Initialize device
    await device.initialize()

    print(f"UID: {device.uid:012X}")
    print(f"Manufacturer: {device.state.manufacturer}")
    print(f"Model: {device.state.model}")
    print(f"Device Label: {device.state.device_label}")
    print(f"Software Version: {device.state.software_version}")
    print(f"RDM Protocol: {device.state.rdm_protocol_version}")
    print(f"DMX Address: {device.state.dmx_start_address}")
    print(f"DMX Footprint: {device.state.dmx_footprint}")
    print(f"Personality: {device.state.dmx_personality}/{device.state.dmx_personality_count}")
    print(f"Sensors: {device.state.sensor_count}")
    print(f"Sub-devices: {device.state.sub_device_count}")


async def test_sensors(device):
    """Test sensor APIs."""
    print("\n=== Sensor Testing ===")

    sensor_count = device.state.sensor_count
    print(f"Sensor count: {sensor_count}")

    if sensor_count > 0:
        # Get all sensor definitions
        print("\nSensor Definitions:")
        definitions = await device.sensor_definitions.get_all_sensor_definitions()
        for i, definition in enumerate(definitions):
            print(f"  Sensor {i}:")
            print(f"    Type: {definition.get('type', 'Unknown')}")
            print(f"    Unit: {definition.get('unit', 'Unknown')}")
            print(
                f"    Range: {definition.get('range_min', '?')} - {definition.get('range_max', '?')}"
            )

        # Get sensor values
        print("\nSensor Values:")
        for i in range(min(3, sensor_count)):  # Test first 3 sensors
            data = await device.sensors.get_value(i)
            if data:
                print(f"  Sensor {i}:")
                print(f"    Present: {data['present_value']}")
                print(f"    Low: {data['lowest']}")
                print(f"    High: {data['highest']}")
                print(f"    Recorded: {data['recorded']}")


async def test_dmx_config(device):
    """Test DMX configuration APIs."""
    print("\n=== DMX Configuration Testing ===")

    # Get personality
    personality = await device.dmx_config.get_personality(use_cache=False)
    if personality:
        current, count = personality
        print(f"Personality: {current}/{count}")

    # Get/Set DMX address
    original_addr = device.state.dmx_start_address
    print(f"Current DMX address: {original_addr}")

    test_addr = 100
    print(f"\nSetting DMX address to {test_addr}...")
    success = await device.dmx_config.set_start_address(test_addr)
    print(f"Result: {'Success' if success else 'Failed'}")

    if success:
        # Verify
        await device.get_device_info(use_cache=False)
        print(f"Verified address: {device.state.dmx_start_address}")

        # Restore
        print(f"\nRestoring DMX address to {original_addr}...")
        await device.dmx_config.set_start_address(original_addr)


async def test_device_label(device):
    """Test device label APIs."""
    print("\n=== Device Label Testing ===")

    # Get current label
    label = await device.device_label.get(use_cache=False)
    print(f"Current label: '{label}'")

    # Set new label
    import datetime

    test_label = f"TEST_{datetime.datetime.now().strftime('%H%M%S')}"
    print(f"\nSetting label to '{test_label}'...")
    success = await device.device_label.set(test_label)
    print(f"Result: {'Success' if success else 'Failed'}")

    if success:
        # Verify
        new_label = await device.device_label.get(use_cache=False)
        print(f"Verified label: '{new_label}'")

        # Restore
        print(f"\nRestoring label to '{label}'...")
        await device.device_label.set(label)


async def test_identify(device):
    """Test identify function."""
    print("\n=== Identify Testing ===")

    print("Turning identify ON (device should blink)...")
    success = await device.control.identify(enable=True)
    print(f"Result: {'Success' if success else 'Failed'}")

    if success:
        print("Waiting 3 seconds...")
        await asyncio.sleep(3)

        print("Turning identify OFF...")
        await device.control.identify(enable=False)


async def test_slots(device):
    """Test DMX slot APIs."""
    print("\n=== DMX Slots Testing ===")

    # Get slot info
    slot_info = await device.slots.get_slot_info()
    if slot_info:
        print(f"Slot info: {len(slot_info)} slots")

    # Get slot descriptions
    descriptions = await device.slots.get_all_slot_descriptions()
    if descriptions:
        print(f"\nSlot Descriptions ({len(descriptions)} total):")
        for i, desc in enumerate(descriptions[:5]):  # Show first 5
            print(f"  Slot {i}: {desc}")
        if len(descriptions) > 5:
            print(f"  ... and {len(descriptions) - 5} more")


async def test_maintenance(device):
    """Test maintenance APIs."""
    print("\n=== Maintenance Testing ===")

    # Get device hours
    hours = await device.maintenance.get_hours(use_cache=False)
    if hours is not None:
        print(f"Device hours: {hours}")
    else:
        print("Device hours: Not supported")

    # Get power cycles
    cycles = await device.maintenance.get_power_cycles(use_cache=False)
    if cycles is not None:
        print(f"Power cycles: {cycles}")
    else:
        print("Power cycles: Not supported")


async def test_system_info(device):
    """Test system info APIs."""
    print("\n=== System Info Testing ===")

    # Get supported parameters
    pids = await device.system.get_supported_parameters(use_cache=False)
    if pids:
        print(f"Supported PIDs: {len(pids)} total")
        print(f"First 20 PIDs: {[hex(p) for p in pids[:20]]}")

    # Get language
    language = await device.system.get_language(use_cache=False)
    if language:
        print(f"Current language: '{language}'")


async def test_all(device):
    """Run all quick tests."""
    await test_basic_info(device)
    await test_sensors(device)
    await test_dmx_config(device)
    await test_device_label(device)
    await test_identify(device)
    await test_slots(device)
    await test_maintenance(device)
    await test_system_info(device)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Quick RDM Device API Test")
    parser.add_argument("--port", type=str, help="Serial port (e.g., COM3)")
    parser.add_argument(
        "--test",
        type=str,
        choices=[
            "info",
            "sensors",
            "dmx",
            "label",
            "identify",
            "slots",
            "maintenance",
            "system",
            "all",
        ],
        default="all",
        help="Which test to run",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Setup
    config = NetworkConfig(port=args.port)
    manager = NetworkManager(config)

    try:
        await manager.start()
        print(f"Connected to port: {manager._config.port}")

        # Discover devices
        devices = await manager.discover_devices()

        if not devices:
            print("ERROR: No devices found. Please connect an RDM device.")
            return

        device = devices[0]
        print(f"Testing device: UID={device.uid:012X}")

        # Run selected test
        test_map = {
            "info": test_basic_info,
            "sensors": test_sensors,
            "dmx": test_dmx_config,
            "label": test_device_label,
            "identify": test_identify,
            "slots": test_slots,
            "maintenance": test_maintenance,
            "system": test_system_info,
            "all": test_all,
        }

        await test_map[args.test](device)

        print("\n" + "=" * 50)
        print("Test completed successfully!")
        print("=" * 50)

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
