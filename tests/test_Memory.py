#!/usr/bin/env python

""" Testing Memory class
"""

from interface_expander.InterfaceExpander import InterfaceExpander
from interface_expander.I2cInterface import I2cInterface, I2cConfig, ClockFreq, AddressWidth, I2cId, I2C_MAX_WRITE_SIZE
from interface_expander.Memory import Memory, MemoryType, MemoryAddressWidth
from tests.helper import generate_ascii_data
from intelhex import IntelHex
from time import sleep
import random
import os

class TestMemory:
    WRITE_READ_COUNT = 1000
    DATA_SIZE_MIN = 1
    DATA_SIZE_MAX = I2C_MAX_WRITE_SIZE + 42

    FRAM_SLAVE_ADDR = 0x50
    FRAM_SIZE = 32768  # (== 2^15)

    def test_slave_address_packing(self):
        address_width = MemoryAddressWidth.TWO_BYTES
        mem = Memory(interface=None, slave_address=TestMemory.FRAM_SLAVE_ADDR, memory_type=MemoryType.FRAM,
                     address_width=address_width, page_count=1, page_size=pow(2, 17))

        address = pow(2, address_width.value * 8) - 1
        mem._pack_slave_address(address) # Should not change the slave address
        assert mem.slave_address == TestMemory.FRAM_SLAVE_ADDR

        # If the memory size is larger than 2^16, the additional address bits will 
        # be packed into the slave address byte.
        address = pow(2, address_width.value * 8)
        mem._pack_slave_address(address)
        assert mem.slave_address == 0b0101_0010  # 0x50 with additional address bit set

        address = pow(2, address_width.value * 8) - 1
        mem._pack_slave_address(address) # Should not change the slave address
        assert mem.slave_address == TestMemory.FRAM_SLAVE_ADDR

    def test_memory_write_read(self):
        expander = InterfaceExpander()
        expander.connect()

        cfg0 = I2cConfig(clock_freq=ClockFreq.FREQ1M,
                        slave_addr=0x01,
                        slave_addr_width=AddressWidth.Bits7)
        i2c0 = I2cInterface(i2c_id=I2cId.I2C0, config=cfg0)

        mem = Memory(interface=i2c0, slave_address=TestMemory.FRAM_SLAVE_ADDR, memory_type=MemoryType.FRAM,
                    address_width=MemoryAddressWidth.TWO_BYTES, page_count=1, page_size=TestMemory.FRAM_SIZE)
        
        for i in range(TestMemory.WRITE_READ_COUNT):
            data = generate_ascii_data(TestMemory.DATA_SIZE_MIN, TestMemory.DATA_SIZE_MAX)
            address = random.randint(0, TestMemory.FRAM_SIZE - len(data))

            mem.write(address=address, data=data)
            mem.flush()
            read_data = mem.read(address=address, length=len(data))

            assert read_data == data, f"Data mismatch at address {address}: expected {data}, got {read_data}"

    def test_memory_down_and_upload_bin_file(self):
        expander = InterfaceExpander()
        expander.connect()

        cfg0 = I2cConfig(clock_freq=ClockFreq.FREQ1M,
                         slave_addr=0x01,
                         slave_addr_width=AddressWidth.Bits7)
        i2c0 = I2cInterface(i2c_id=I2cId.I2C0, config=cfg0)

        mem = Memory(interface=i2c0, slave_address=TestMemory.FRAM_SLAVE_ADDR, memory_type=MemoryType.FRAM,
                     address_width=MemoryAddressWidth.TWO_BYTES, page_count=1, page_size=TestMemory.FRAM_SIZE)

        # Generate random bin file for testing
        random_data = generate_ascii_data(TestMemory.FRAM_SIZE, TestMemory.FRAM_SIZE)
        with open(r"littlefs_image.bin", "wb") as f:
            f.write(random_data)

        mem.upload_bin_file(0, r"littlefs_image.bin")  # file -> mem
        os.remove(r"littlefs_image.bin")
        sleep(0.1)
        mem.download_bin_file(0, r"littlefs_image.bin")  # mem -> file

        # Check if the data matches
        with open(r"littlefs_image.bin", "rb") as f:
            read_data = f.read()
        assert read_data == random_data

        os.remove(r"littlefs_image.bin")

    def test_memory_down_and_upload_hex_file(self):
        expander = InterfaceExpander()
        expander.connect()

        cfg0 = I2cConfig(clock_freq=ClockFreq.FREQ1M,
                         slave_addr=0x01,
                         slave_addr_width=AddressWidth.Bits7)
        i2c0 = I2cInterface(i2c_id=I2cId.I2C0, config=cfg0)

        mem = Memory(interface=i2c0, slave_address=TestMemory.FRAM_SLAVE_ADDR, memory_type=MemoryType.FRAM,
                     address_width=MemoryAddressWidth.TWO_BYTES, page_count=1, page_size=TestMemory.FRAM_SIZE)

        # Generate random hex file for testing
        random_data = generate_ascii_data(TestMemory.FRAM_SIZE, TestMemory.FRAM_SIZE)
        ih = IntelHex()
        ih.puts(0, random_data)
        ih.write_hex_file('littlefs_image.hex')

        mem.upload_hex_file(r"littlefs_image.hex")  # file -> mem
        os.remove(r"littlefs_image.hex")
        sleep(0.1)
        mem.download_hex_file(0, r"littlefs_image.hex")  # mem -> file

        ih = IntelHex()
        ih.loadhex(r"littlefs_image.hex")  # Load the HEX file
        read_data = bytes(ih.tobinarray())

        assert read_data == random_data

        os.remove(r"littlefs_image.hex")
