import os
import sys
import logging
import struct
import threading
import time
from ctypes import CDLL, c_void_p, c_char_p, c_int, c_ssize_t, create_string_buffer

logger = logging.getLogger(__name__)

class VirtualController:
    """
    Virtual controller implementation using foohid for macOS
    """
    def __init__(self):
        self.is_initialized = False
        self.is_running = False
        self.foohid = None
        self.device_name = b"DuoSenseVirtualController"
        self.serial_number = b"1234567890"
        self.hid_report = create_string_buffer(64)
        self.lock = threading.Lock()
        
        # HID Report Descriptor for Xbox-like controller
        self.report_descriptor = bytes([
            0x05, 0x01,        # Usage Page (Generic Desktop)
            0x09, 0x05,        # Usage (Game Pad)
            0xA1, 0x01,        # Collection (Application)
            0x85, 0x01,        # Report ID (1)
            # Buttons (2 bytes)
            0x05, 0x09,        # Usage Page (Button)
            0x19, 0x01,        # Usage Minimum (1)
            0x29, 0x10,        # Usage Maximum (16)
            0x15, 0x00,        # Logical Minimum (0)
            0x25, 0x01,        # Logical Maximum (1)
            0x75, 0x01,        # Report Size (1)
            0x95, 0x10,        # Report Count (16)
            0x81, 0x02,        # Input (Data,Var,Abs)
            # Axes (4 axes, 8 bits each)
            0x05, 0x01,        # Usage Page (Generic Desktop)
            0x09, 0x30,        # Usage (X)
            0x09, 0x31,        # Usage (Y)
            0x09, 0x32,        # Usage (Z)
            0x09, 0x35,        # Usage (Rz)
            0x16, 0x00, 0x00,  # Logical Minimum (0)
            0x26, 0xFF, 0x00,  # Logical Maximum (255)
            0x75, 0x08,        # Report Size (8)
            0x95, 0x04,        # Report Count (4)
            0x81, 0x02,        # Input (Data,Var,Abs)
            # Triggers (2 triggers, 8 bits each)
            0x09, 0x33,        # Usage (Rx)
            0x09, 0x34,        # Usage (Ry)
            0x95, 0x02,        # Report Count (2)
            0x81, 0x02,        # Input (Data,Var,Abs)
            0xC0              # End Collection
        ])

        try:
            self.foohid = CDLL('/usr/local/lib/libfoohid.dylib')
            self.foohid.foohid_create.argtypes = [c_char_p, c_char_p, c_int, 
                                                 c_int, c_char_p, c_int]
            self.foohid.foohid_send.argtypes = [c_char_p, c_char_p, c_ssize_t]
            self.is_initialized = True
            logger.info("Foohid initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize foohid: {e}")

    def start(self):
        if not self.is_initialized:
            return False

        res = self.foohid.foohid_create(
            self.device_name,
            self.serial_number,
            len(self.report_descriptor),
            2,  # Number of reports
            self.report_descriptor,
            len(self.report_descriptor))
        
        if res != 0:
            logger.error("Failed to create virtual controller")
            return False

        self.is_running = True
        logger.info("Virtual controller started")
        return True

    def stop(self):
        if self.is_running:
            self.foohid.foohid_destroy(self.device_name)
            self.is_running = False
            logger.info("Virtual controller stopped")

    def update_state(self, buttons, axes):
        with self.lock:
            # Map DualSense inputs to standard controller layout
            # Buttons mapping
            button_map = {
                'button_0': 0,   # Cross/A
                'button_1': 1,   # Circle/B
                'button_2': 2,   # Square/X
                'button_3': 3,   # Triangle/Y
                'button_4': 4,   # L1
                'button_5': 5,   # R1
                'button_8': 6,   # Share
                'button_9': 7,   # Options
                'button_10': 8,  # L3
                'button_11': 9,  # R3
                'button_12': 10, # PS
                'hat_0_up': 11,  # D-pad Up
                'hat_0_down': 12, # D-pad Down
                'hat_0_left': 13, # D-pad Left
                'hat_0_right': 14, # D-pad Right
            }

            # Create button bitmask
            button_state = 0
            for btn, pos in button_map.items():
                if buttons.get(btn, False):
                    button_state |= 1 << pos

            # Process analog sticks and triggers
            lx = self._scale_axis(axes.get('axis_0', 0.0))
            ly = self._scale_axis(axes.get('axis_1', 0.0))
            rx = self._scale_axis(axes.get('axis_2', 0.0))
            ry = self._scale_axis(axes.get('axis_3', 0.0))
            lt = self._scale_trigger(axes.get('axis_4', 0.0))
            rt = self._scale_trigger(axes.get('axis_5', 0.0))

            # Build HID report (Little Endian)
            report = struct.pack('<HBBBBBB',
                0x01,  # Report ID
                button_state & 0xFF,
                (button_state >> 8) & 0xFF,
                lx, ly, rx, ry,
                lt, rt)

            # Update the HID report buffer
            self.hid_report.value = report

    def _scale_axis(self, value):
        """Scale from -1.0 to 1.0 to 0-255"""
        return int((value + 1.0) * 127.5) & 0xFF

    def _scale_trigger(self, value):
        """Scale from -1.0 to 1.0 to 0-255"""
        return int((value + 1.0) * 127.5) & 0xFF

    def _output_loop(self):
        while self.is_running:
            with self.lock:
                if self.hid_report:
                    self.foohid.foohid_send(
                        self.device_name,
                        self.hid_report,
                        len(self.hid_report))
            time.sleep(0.01)