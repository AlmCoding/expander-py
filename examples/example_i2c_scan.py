from interface_expander.InterfaceExpander import InterfaceExpander
from interface_expander.I2cInterface import I2cInterface, I2cConfig, ClockFreq, AddressWidth, I2cId, I2cMasterRequest


if __name__ == "__main__":
    expander = InterfaceExpander()
    expander.connect()

    cfg0 = I2cConfig(clock_freq=ClockFreq.FREQ400K, slave_addr=0x01, slave_addr_width=AddressWidth.Bits7)
    i2c0 = I2cInterface(i2c_id=I2cId.I2C0, config=cfg0)

    cfg1 = I2cConfig(clock_freq=ClockFreq.FREQ400K, slave_addr=0x02, slave_addr_width=AddressWidth.Bits7)
    i2c1 = I2cInterface(i2c_id=I2cId.I2C1, config=cfg1)

    for slave_addr in i2c0.slave_scan():
        print(f"Found device at address 0x{slave_addr:02X}")

    expander.disconnect()
