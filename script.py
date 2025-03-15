from msg.InterfaceExpander import InterfaceExpander
from msg.I2cInterface import I2cInterface, I2cConfig, ClockFreq, AddressWidth, I2cId, I2cMasterRequest


if __name__ == "__main__":
    expander = InterfaceExpander()
    expander.reset()
    expander.connect()

    cfg0 = I2cConfig(clock_freq=ClockFreq.FREQ400K,
                     slave_addr=0x01,
                     slave_addr_width=AddressWidth.Bits7,
                     mem_addr_width=AddressWidth.Bits16)
    cfg1 = I2cConfig(clock_freq=ClockFreq.FREQ400K,
                     slave_addr=0x02,
                     slave_addr_width=AddressWidth.Bits7,
                     mem_addr_width=AddressWidth.Bits16)

    i2c0 = I2cInterface(i2c_id=I2cId.I2C0, config=cfg0)
    i2c1 = I2cInterface(i2c_id=I2cId.I2C1, config=cfg1)

    request = I2cMasterRequest(slave_addr=0x50, write_data=bytes([0x00, 0x01, 0x42]), read_size=0)
    rid = i2c0.send_request(request=request)
    i2c0.wait_for_response(request_id=rid, timeout=1000)

    rid = i2c1.send_request(request=request)
    i2c1.wait_for_response(request_id=rid, timeout=1000)

    expander.disconnect()

    exit(0)
