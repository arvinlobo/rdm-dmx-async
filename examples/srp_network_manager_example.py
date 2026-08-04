"""
Example demonstrating SRP-compliant NetworkManager usage.

NetworkManager now strictly follows SRP - it only handles network lifecycle.
All device and batch operations go through dedicated services.
"""

import asyncio

from rdm_dmx_async import NetworkConfig, NetworkManager


async def example_basic_usage():
    """Basic example using SRP-compliant API."""

    # Auto-detect Enttec port
    config = NetworkConfig()

    async with NetworkManager(config) as manager:
        print(f"Connected to {manager._config.port}")

        # Discover all devices on network
        devices = await manager.discover_devices()
        print(f"Discovered {len(devices)} devices")

        # === SRP-COMPLIANT API (ONLY WAY TO ACCESS) ===

        # Access devices via device manager
        print("\n--- Device Manager ---")
        for uid in manager.devices.get_all_uids():
            device = manager.devices.get_device(uid)
            print(f"Device: {device.state.device_label} [{uid:012X}]")

        # Batch operations via batch service
        print("\n--- Batch Operations ---")
        labels = await manager.batch.query_all_device_labels()
        for uid, label in labels.items():
            print(f"  {uid:012X}: {label}")

        # Set all DMX addresses
        results = await manager.batch.set_all_dmx_addresses(start_address=1, spacing=10)
        print(f"\nSet DMX addresses: {sum(results.values())}/{len(results)} succeeded")

        # Identify all devices
        print("\nIdentifying all devices...")
        await manager.batch.identify_all(enable=True)
        await asyncio.sleep(3)
        await manager.batch.identify_all(enable=False)

        # Clear caches
        manager.devices.clear_all_caches()
        print(f"\nCleared caches for {manager.devices.get_device_count()} devices")


async def example_individual_device_operations():
    """Example working with individual devices."""

    config = NetworkConfig(port="COM3")  # Or None for auto-detect

    async with NetworkManager(config) as manager:
        devices = await manager.discover_devices()

        if not devices:
            print("No devices found")
            return

        # Get first device via device manager
        uid = manager.devices.get_all_uids()[0]
        device = manager.devices.get_device(uid)

        if device:
            print(f"\nWorking with device: {device.state.device_label}")

            # Get device info
            await device.get_device_info()
            print(f"  Manufacturer: {device.state.manufacturer}")
            print(f"  Software Version: {device.state.software_version}")
            print(f"  DMX Address: {device.state.dmx_start_address}")

            # Set DMX address
            success = await device.dmx_config.set_start_address(100)
            print(f"  Set address to 100: {'Success' if success else 'Failed'}")

            # Identify
            await device.control.identify(enable=True)
            await asyncio.sleep(2)
            await device.control.identify(enable=False)


async def example_direct_service_usage():
    """Example using services independently (advanced)."""

    from rdm_dmx_async import BatchOperationService, DeviceCollectionManager, PortDetectionService

    # Use port detector independently
    print("--- Port Detection Service ---")
    port_detector = PortDetectionService()
    port = port_detector.auto_detect_enttec()
    print(f"Detected port: {port}")

    all_ports = port_detector.list_all_ports()
    print(f"Available ports: {all_ports}")

    # Create device manager independently
    print("\n--- Device Collection Manager ---")
    device_manager = DeviceCollectionManager()
    print(f"Device count: {device_manager.get_device_count()}")

    # Create batch operations service
    print("\n--- Batch Operation Service ---")
    _batch_ops = BatchOperationService(device_manager)
    print("Batch service ready (requires devices to be added)")


async def example_known_devices():
    """Example discovering specific known devices."""

    config = NetworkConfig()

    async with NetworkManager(config) as manager:
        # Discover specific UIDs instead of full network scan
        known_uids = [
            0x454E00000001,  # Example UIDs
            0x454E00000002,
        ]

        devices = await manager.discover_devices(known_uids=known_uids)
        print(f"Found {len(devices)} of {len(known_uids)} known devices")

        # Query info for discovered devices
        device_info = await manager.batch.query_all_device_info()

        for uid, info in device_info.items():
            print(f"\n{uid:012X}:")
            print(f"  Label: {info['device_label']}")
            print(f"  Model: {info['device_model_id']}")
            print(f"  Address: {info['dmx_start_address']}")


async def main():
    """Run examples."""

    print("=" * 60)
    print("SRP-Compliant Network Manager Example")
    print("=" * 60)
    await example_basic_usage()

    print("\n" + "=" * 60)
    print("Individual Device Operations")
    print("=" * 60)
    await example_individual_device_operations()

    print("\n" + "=" * 60)
    print("Direct Service Usage")
    print("=" * 60)
    await example_direct_service_usage()

    print("\n" + "=" * 60)
    print("Known Devices Discovery")
    print("=" * 60)
    await example_known_devices()


if __name__ == "__main__":
    asyncio.run(main())
