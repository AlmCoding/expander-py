#!/usr/bin/env python

"""Testing I2c master write/read"""

from interface_expander.InterfaceExpander import InterfaceExpander
from interface_expander.I2cInterface import I2cInterface, I2cConfig, ClockFreq, AddressWidth, I2cId
from tests.helper import generate_master_write_read_requests, i2c_send_request, verify_master_write_read_requests


class TestI2cMaster:
    REQUEST_COUNT = 4 * 2000
    DATA_SIZE_MIN = 1
    DATA_SIZE_MAX = 128

    I2C_CLOCK_FREQ = ClockFreq.FREQ400K
    I2C0_SLAVE_ADDR = 0x01
    I2C1_SLAVE_ADDR = 0x02
    FRAM_SLAVE_ADDR = 0x51

    FRAM_SIZE = 32768  # (== 2^15)
    FRAM_0_MIN_ADDR = 0
    FRAM_0_MAX_ADDR = FRAM_SIZE // 2 - 1
    FRAM_1_MIN_ADDR = FRAM_SIZE // 2
    FRAM_1_MAX_ADDR = FRAM_SIZE - 1

    def test_i2c_master_slave_scan(self):
        expander = InterfaceExpander()
        expander.reset()
        expander.connect()

        cfg0 = I2cConfig(clock_freq=ClockFreq.FREQ400K, slave_addr=0x01, slave_addr_width=AddressWidth.Bits7)
        i2c0 = I2cInterface(i2c_id=I2cId.I2C0, config=cfg0)

        cfg1 = I2cConfig(clock_freq=ClockFreq.FREQ400K, slave_addr=0x02, slave_addr_width=AddressWidth.Bits7)
        _ = I2cInterface(i2c_id=I2cId.I2C1, config=cfg1)
        for slave_addr in i2c0.slave_scan():
            print(f"Found device at address 0x{slave_addr:02X}")

        expander.disconnect()

    def test_i2c_master_write_read_fram(self):
        # Test master using external FRAM
        expander = InterfaceExpander()
        expander.reset()
        expander.connect()

        cfg0 = I2cConfig(
            clock_freq=TestI2cMaster.I2C_CLOCK_FREQ,
            slave_addr=0x01,
            slave_addr_width=AddressWidth.Bits7,
            mem_addr_width=AddressWidth.Bits16,
        )
        cfg1 = I2cConfig(
            clock_freq=TestI2cMaster.I2C_CLOCK_FREQ,
            slave_addr=0x02,
            slave_addr_width=AddressWidth.Bits7,
            mem_addr_width=AddressWidth.Bits16,
        )

        i2c0 = I2cInterface(i2c_id=I2cId.I2C0, config=cfg0, callback_fn=None)
        i2c1 = I2cInterface(i2c_id=I2cId.I2C1, config=cfg1, callback_fn=None)

        requests_pipeline0 = generate_master_write_read_requests(
            slave_addr=TestI2cMaster.FRAM_SLAVE_ADDR,
            min_addr=TestI2cMaster.FRAM_0_MIN_ADDR,
            max_addr=TestI2cMaster.FRAM_0_MAX_ADDR,
            min_size=TestI2cMaster.DATA_SIZE_MIN,
            max_size=TestI2cMaster.DATA_SIZE_MAX,
            count=TestI2cMaster.REQUEST_COUNT // 4,
        )
        requests_pipeline1 = generate_master_write_read_requests(
            slave_addr=TestI2cMaster.FRAM_SLAVE_ADDR,
            min_addr=TestI2cMaster.FRAM_1_MIN_ADDR,
            max_addr=TestI2cMaster.FRAM_1_MAX_ADDR,
            min_size=TestI2cMaster.DATA_SIZE_MIN,
            max_size=TestI2cMaster.DATA_SIZE_MAX,
            count=TestI2cMaster.REQUEST_COUNT // 4,
        )

        while len(requests_pipeline0) > 0:
            rid = i2c_send_request(i2c0, requests_pipeline0)
            i2c0.wait_for_response(request_id=rid, timeout=0.1)
            verify_master_write_read_requests(i2c0)

        while len(requests_pipeline1) > 0:
            rid = i2c_send_request(i2c1, requests_pipeline1)
            i2c1.wait_for_response(request_id=rid, timeout=0.1)
            verify_master_write_read_requests(i2c1)

        expander.disconnect()
