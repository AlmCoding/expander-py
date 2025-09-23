from interface_expander.InterfaceExpander import InterfaceExpander
from interface_expander.I2cInterface import I2cInterface, I2cConfig, ClockFreq, AddressWidth, I2cId, I2cMasterRequest


if __name__ == "__main__":
    expander = InterfaceExpander()
    expander.connect()

    cfg0 = I2cConfig(clock_freq=ClockFreq.FREQ1M,
                     slave_addr=0x01,
                     slave_addr_width=AddressWidth.Bits7)
    i2c0 = I2cInterface(i2c_id=I2cId.I2C0, config=cfg0)

    request = I2cMasterRequest(slave_addr=0x51,
                               write_data=bytes([0x00, 0x42]),
                               read_size=128)
    rid = i2c0.send_request(request=request)
    req = i2c0.wait_for_response(request_id=rid, timeout=0.02)

    print(f"Request (rid: {req.request_id}, status: {req.status_code}, "
          f"write_data: {req.write_data}, read_data: {req.read_data})")

    expander.disconnect()
