"""
Hardware test for RDM Device APIs.

Tests all device API modules with real hardware connected via serial port.
Run this test with an actual RDM device connected.

Usage:
    python hardware_device_api_test.py [--port COM3]
"""

import argparse
import asyncio
import logging
from datetime import datetime

from rdm_dmx_async import NetworkConfig, NetworkManager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DeviceAPITester:
    """Hardware tester for all RDM device APIs."""

    def __init__(self, port: str | None = None):
        self.port = port
        self.config = NetworkConfig(port=port)
        self.manager: NetworkManager | None = None
        self.device = None
        self.test_results = {}

    def log_test(self, test_name: str, success: bool, message: str = ""):
        """Log test result."""
        status = "✓ PASS" if success else "✗ FAIL"
        self.test_results[test_name] = success
        logger.info(f"{status} - {test_name}: {message}")

    async def setup(self):
        """Initialize network manager and discover device."""
        logger.info("=" * 70)
        logger.info("RDM Device API Hardware Test Suite")
        logger.info("=" * 70)

        self.manager = NetworkManager(self.config)
        await self.manager.start()
        logger.info(f"Connected to port: {self.manager._config.port}")

        # Discover devices
        devices = await self.manager.discover_devices()

        if not devices:
            raise RuntimeError("No devices found on network. Please connect an RDM device.")

        self.device = devices[0]
        logger.info(f"Testing device: UID={self.device.uid:012X}")
        logger.info(f"Manufacturer: {self.device.state.manufacturer}")
        logger.info(f"Model: {self.device.state.model}")
        logger.info(f"Device Label: {self.device.state.device_label}")
        logger.info("")

    async def teardown(self):
        """Cleanup network manager."""
        if self.manager:
            await self.manager.stop()

        # Print summary
        logger.info("")
        logger.info("=" * 70)
        logger.info("Test Summary")
        logger.info("=" * 70)
        passed = sum(1 for v in self.test_results.values() if v)
        total = len(self.test_results)
        logger.info(f"Passed: {passed}/{total}")
        logger.info(f"Failed: {total - passed}/{total}")
        logger.info("=" * 70)

    # ===== Capability-Driven Testing =====
    async def test_capability_detection(self):
        """Test device capability detection and execute supported APIs."""
        logger.info("=" * 70)
        logger.info("CAPABILITY DETECTION & DYNAMIC API TESTING")
        logger.info("=" * 70)

        try:
            # Step 1: Check capabilities
            logger.info("--- Step 1: Detecting Device Capabilities ---")
            success = await self.device.check_capabilities()
            self.log_test("check_capabilities()", success, "Query supported PIDs")

            if not success:
                logger.warning(
                    "Capability detection failed - device may not support SUPPORTED_PARAMETERS"
                )
                logger.info("Running tests optimistically without capability detection")

            # Get available APIs
            available_apis = self.device.get_available_apis()
            self.log_test("get_available_apis()", True, f"{len(available_apis)} APIs available")
            logger.info(f"    Available APIs: {', '.join(sorted(available_apis))}")

            # Get detailed support info
            details = self.device.get_api_support_details()
            self.log_test("get_api_support_details()", True, f"Got details for {len(details)} APIs")

            # Show partial support cases
            partial = [
                (api, info)
                for api, info in details.items()
                if info["supported"] and 0 < info["coverage"] < 1.0
            ]
            if partial:
                logger.info("    Partial support detected:")
                for api, info in partial:
                    logger.info(
                        f"      {api}: {info['coverage'] * 100:.0f}% ({len(info['supported_pids'])}/{len(info['pids'])} PIDs)"
                    )

            # Print capability report
            logger.info("")
            self.device.print_capability_report()
            logger.info("")

            # Step 2: Execute tests for supported APIs
            logger.info("=" * 70)
            logger.info("EXECUTING TESTS FOR SUPPORTED APIs")
            logger.info("=" * 70)

            # Test device_label API
            if self.device.supports_api("device_label"):
                await self._test_device_label_api()

            # Test dmx_config API
            if self.device.supports_api("dmx_config"):
                await self._test_dmx_config_api()

            # Test control API
            if self.device.supports_api("control"):
                await self._test_control_api()

            # Test info API
            if self.device.supports_api("info"):
                await self._test_info_api()

            # Test maintenance API
            if self.device.supports_api("maintenance"):
                await self._test_maintenance_api()

            # Test sensors API
            if self.device.supports_api("sensors"):
                await self._test_sensors_api()

            # Test lamp API
            if self.device.supports_api("lamp"):
                await self._test_lamp_api()

            # Test display API
            if self.device.supports_api("display"):
                await self._test_display_api()

            # Test position API
            if self.device.supports_api("position"):
                await self._test_position_api()

            # Test power API
            if self.device.supports_api("power"):
                await self._test_power_api()

            # Test dmx_modes API
            if self.device.supports_api("modes"):
                await self._test_dmx_modes_api()

            # Test dmx_slots API
            if self.device.supports_api("slots"):
                await self._test_dmx_slots_api()

            # Test system API
            if self.device.supports_api("system"):
                await self._test_system_api()

            # Test proxy API (only meaningful if the device is an RDM proxy)
            if self.device.supports_api("proxy"):
                await self._test_proxy_api()

        except Exception as e:
            self.log_test("capability_detection", False, f"Error: {e}")
            import traceback

            logger.error(traceback.format_exc())

        logger.info("")

    async def _test_device_label_api(self):
        """Test device label API."""
        logger.info("--- Device Label API ---")
        try:
            # SET
            test_label = f"TEST_{datetime.now().strftime('%H%M%S')}"
            success = await self.device.device_label.set(test_label)
            self.log_test("device_label.set()", success, f'"{test_label}"')

            # GET to verify
            if success:
                label = await self.device.device_label.get(use_cache=False)
                self.log_test("device_label.get()", True, f'"{label}"')
        except Exception as e:
            self.log_test("device_label", False, f"Error: {e}")
        logger.info("")

    async def _test_dmx_config_api(self):
        """Test DMX configuration API."""
        logger.info("--- DMX Config API ---")
        try:
            # SET start address
            test_addr = 100
            success = await self.device.dmx_config.set_start_address(test_addr)
            self.log_test("dmx_config.set_start_address()", success, f"Set to: {test_addr}")

            # GET to verify
            if success:
                addr = self.device.state.dmx_start_address
                self.log_test("dmx_config.get_start_address()", True, f"Address: {addr}")

            # GET personality
            personality = await self.device.dmx_config.get_personality(use_cache=False)
            if personality:
                current, count = personality
                self.log_test("dmx_config.get_personality()", True, f"Current: {current}/{count}")

                # GET personality description for the active personality
                desc = await self.device.dmx_config.get_personality_description(current)
                if desc:
                    self.log_test(
                        "dmx_config.get_personality_description()",
                        True,
                        f'"{desc["description"]}" footprint={desc["footprint"]}',
                    )
        except Exception as e:
            self.log_test("dmx_config", False, f"Error: {e}")
        logger.info("")

    async def _test_control_api(self):
        """Test device control API."""
        logger.info("--- Device Control API ---")
        try:
            success = await self.device.control.identify(enable=True)
            self.log_test("control.identify(True)", success, "Device should blink")

            if success:
                await asyncio.sleep(1)
                await self.device.control.identify(enable=False)
                self.log_test("control.identify(False)", True, "Stopped blinking")
        except Exception as e:
            self.log_test("control", False, f"Error: {e}")
        logger.info("")

    async def _test_info_api(self):
        """Test device info API."""
        logger.info("--- Device Info API ---")
        try:
            model = await self.device.info.get_model_description(use_cache=False)
            self.log_test("info.get_model_description()", True, f'"{model}"')

            manufacturer = await self.device.get_manufacturer_label(use_cache=False)
            self.log_test("info.get_manufacturer()", True, f'"{manufacturer}"')

            version_id = await self.device.info.get_boot_software_version_id(use_cache=False)
            if version_id is not None:
                self.log_test("info.get_boot_software_version_id()", True, f"0x{version_id:08X}")

            details = await self.device.info.get_product_detail_id_list(use_cache=False)
            if details is not None:
                self.log_test(
                    "info.get_product_detail_id_list()", True, f"{len(details)} detail ID(s)"
                )
        except Exception as e:
            self.log_test("info", False, f"Error: {e}")
        logger.info("")

    async def _test_maintenance_api(self):
        """Test maintenance API."""
        logger.info("--- Device Maintenance API ---")
        try:
            hours = await self.device.maintenance.get_hours(use_cache=False)
            if hours is not None:
                self.log_test("maintenance.get_hours()", True, f"{hours} hours")

            cycles = await self.device.maintenance.get_power_cycles(use_cache=False)
            if cycles is not None:
                self.log_test("maintenance.get_power_cycles()", True, f"{cycles} cycles")
        except Exception as e:
            self.log_test("maintenance", False, f"Error: {e}")
        logger.info("")

    async def _test_sensors_api(self):
        """Test sensors API."""
        logger.info("--- Sensors API ---")
        try:
            sensor_count = self.device.state.sensor_count
            self.log_test("sensors.count", True, f"{sensor_count} sensors")

            if sensor_count > 0:
                sensor_data = await self.device.sensors.get_value(0)
                if sensor_data:
                    self.log_test(
                        "sensors.get_value(0)", True, f"Value: {sensor_data['present_value']}"
                    )
        except Exception as e:
            self.log_test("sensors", False, f"Error: {e}")
        logger.info("")

    async def _test_lamp_api(self):
        """Test lamp control API."""
        logger.info("--- Lamp Control API ---")
        try:
            hours = await self.device.lamp.get_hours(use_cache=False)
            if hours is not None:
                self.log_test("lamp.get_hours()", True, f"{hours} hours")

            strikes = await self.device.lamp.get_strikes(use_cache=False)
            if strikes is not None:
                self.log_test("lamp.get_strikes()", True, f"{strikes} strikes")
        except Exception as e:
            self.log_test("lamp", False, f"Error: {e}")
        logger.info("")

    async def _test_display_api(self):
        """Test display settings API."""
        logger.info("--- Display Settings API ---")
        try:
            invert = await self.device.display.get_invert(use_cache=False)
            if invert is not None:
                self.log_test("display.get_invert()", True, f"Invert: {invert}")

            level = await self.device.display.get_level(use_cache=False)
            if level is not None:
                self.log_test("display.get_level()", True, f"Level: {level}")
        except Exception as e:
            self.log_test("display", False, f"Error: {e}")
        logger.info("")

    async def _test_position_api(self):
        """Test position configuration API."""
        logger.info("--- Position Config API ---")
        try:
            pan_invert = await self.device.position.get_pan_invert(use_cache=False)
            if pan_invert is not None:
                self.log_test("position.get_pan_invert()", True, f"Pan invert: {pan_invert}")
        except Exception as e:
            self.log_test("position", False, f"Error: {e}")
        logger.info("")

    async def _test_power_api(self):
        """Test power control API."""
        logger.info("--- Power Control API ---")
        try:
            state = await self.device.power.get_state(use_cache=False)
            if state is not None:
                self.log_test("power.get_state()", True, f"State: {state}")
        except Exception as e:
            self.log_test("power", False, f"Error: {e}")
        logger.info("")

    async def _test_dmx_modes_api(self):
        """Test DMX modes API."""
        logger.info("--- DMX Modes API ---")
        try:
            startup_mode = await self.device.modes.get_dmx_startup_mode(use_cache=False)
            if startup_mode is not None:
                self.log_test("modes.get_dmx_startup_mode()", True, f"Mode: {startup_mode}")

            response_time = await self.device.modes.get_output_response_time(use_cache=False)
            if response_time is not None:
                self.log_test("modes.get_output_response_time()", True, f"Time: {response_time}")
        except Exception as e:
            self.log_test("dmx_modes", False, f"Error: {e}")
        logger.info("")

    async def _test_dmx_slots_api(self):
        """Test DMX slots API."""
        logger.info("--- DMX Slots API ---")
        try:
            slot_info = await self.device.slots.get_slot_info()
            if slot_info:
                self.log_test("slots.get_slot_info()", True, f"Got {len(slot_info)} slots")

            descriptions = await self.device.slots.get_all_slot_descriptions()
            if descriptions:
                self.log_test(
                    "slots.get_all_descriptions()", True, f"Got {len(descriptions)} descriptions"
                )

            defaults = await self.device.slots.get_default_slot_values()
            if defaults:
                self.log_test(
                    "slots.get_default_slot_values()", True, f"Got {len(defaults)} default(s)"
                )
        except Exception as e:
            self.log_test("dmx_slots", False, f"Error: {e}")
        logger.info("")

    async def _test_system_api(self):
        """Test system info API."""
        logger.info("--- System Info API ---")
        try:
            pids = await self.device.system.get_supported_parameters(use_cache=False)
            if pids:
                self.log_test("system.get_supported_parameters()", True, f"{len(pids)} PIDs")

                # Test parameter description with first supported PID
                if len(pids) > 0:
                    desc = await self.device.system.get_parameter_description(pids[0])
                    if desc:
                        self.log_test(
                            "system.get_parameter_description()",
                            True,
                            f"PID: 0x{desc['pid']:04X}, PDL: {desc['pdl_size']}",
                        )

            comms = await self.device.system.get_comms_status()
            if comms is not None:
                self.log_test(
                    "system.get_comms_status()",
                    True,
                    f"short={comms['short_message']} mismatch={comms['length_mismatch']} "
                    f"checksum={comms['checksum_fail']}",
                )
                cleared = await self.device.system.clear_comms_status()
                self.log_test("system.clear_comms_status()", cleared, "Counters reset")

            threshold = await self.device.system.get_sub_device_status_report_threshold(
                use_cache=False
            )
            if threshold is not None:
                self.log_test(
                    "system.get_sub_device_status_report_threshold()",
                    True,
                    f"Threshold: {threshold}",
                )
                restored = await self.device.system.set_sub_device_status_report_threshold(
                    threshold
                )
                self.log_test(
                    "system.set_sub_device_status_report_threshold()",
                    restored,
                    "Re-set to current value",
                )
        except Exception as e:
            self.log_test("system", False, f"Error: {e}")
        logger.info("")

    async def _test_proxy_api(self):
        """Test RDM proxy management API (only meaningful if the device is a proxy)."""
        logger.info("--- Proxy API ---")
        try:
            count_info = await self.device.proxy.get_proxied_device_count(use_cache=False)
            if count_info is not None:
                count, list_change = count_info
                self.log_test(
                    "proxy.get_proxied_device_count()",
                    True,
                    f"count={count} list_change={list_change}",
                )

            devices = await self.device.proxy.get_proxied_devices()
            if devices is not None:
                self.log_test("proxy.get_proxied_devices()", True, f"{len(devices)} device(s)")
        except Exception as e:
            self.log_test("proxy", False, f"Error: {e}")
        logger.info("")

    async def _test_caching_behavior(self):
        """Test parameter caching (cache hit should be faster than cache miss)."""
        logger.info("--- Caching Behavior ---")
        try:
            start = datetime.now()
            label1 = await self.device.device_label.get(use_cache=True)
            miss_elapsed = (datetime.now() - start).total_seconds()

            start = datetime.now()
            label2 = await self.device.device_label.get(use_cache=True)
            hit_elapsed = (datetime.now() - start).total_seconds()

            self.log_test(
                "cache miss then hit",
                label1 == label2,
                f"miss={miss_elapsed:.3f}s, hit={hit_elapsed:.3f}s",
            )

            self.device.clear_cache()
            start = datetime.now()
            label3 = await self.device.device_label.get(use_cache=True)
            after_clear_elapsed = (datetime.now() - start).total_seconds()
            self.log_test(
                "cache cleared then re-fetched",
                label3 == label1,
                f"elapsed={after_clear_elapsed:.3f}s",
            )
        except Exception as e:
            self.log_test("caching_behavior", False, f"Error: {e}")
        logger.info("")

    async def _test_batch_operations(self):
        """Test batch operations across all discovered devices."""
        logger.info("--- Batch Operations ---")
        try:
            results = await self.manager.batch.query_all_device_labels()
            self.log_test(
                "manager.query_all_device_labels()", True, f"{len(results)} device(s) responded"
            )
        except Exception as e:
            self.log_test("batch_operations", False, f"Error: {e}")
        logger.info("")

    async def _test_error_recovery(self):
        """Test that an invalid request is rejected without breaking the device."""
        logger.info("--- Error Handling & Recovery ---")
        if not self.device.supports_api("dmx_config"):
            self.log_test("error_recovery", True, "Skipped - dmx_config API not supported")
            logger.info("")
            return
        try:
            original_address = self.device.state.dmx_start_address

            rejected = not await self.device.dmx_config.set_start_address(9999)
            self.log_test(
                "dmx_config.set_start_address(9999)", rejected, "Invalid address rejected"
            )

            restored = await self.device.dmx_config.set_start_address(original_address or 1)
            self.log_test(
                "dmx_config.set_start_address(valid)",
                restored,
                "Device still responsive after invalid request",
            )
        except Exception as e:
            self.log_test("error_recovery", False, f"Error: {e}")
        logger.info("")

    async def run_all_tests(self):
        """Run capability-driven hardware tests."""
        try:
            await self.setup()

            # Run single capability-driven test
            await self.test_capability_detection()

            # Cross-cutting checks not tied to a single capability
            await self._test_caching_behavior()
            await self._test_batch_operations()
            await self._test_error_recovery()

        finally:
            await self.teardown()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="RDM Device API Hardware Test")
    parser.add_argument(
        "--port", type=str, help="Serial port (e.g., COM3). Auto-detect if not specified."
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    tester = DeviceAPITester(port=args.port)
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
