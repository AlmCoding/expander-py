from proto.proto_py import gpio_pb2
from enum import Enum

SEQ_NUM = 0
INPUT_DATA = None
SYNCHRONIZED = True


class GpioId(Enum):
    GPIO0 = 0
    GPIO1 = 1
    GPIO2 = 2
    GPIO3 = 3
    GPIO4 = 4
    GPIO5 = 5
    GPIO6 = 6
    GPIO7 = 7
    GPIO_CNT = 8


class GpioMode(Enum):
    INPUT_PULLDOWN = 0
    INPUT_PULLUP = 1
    INPUT_NOPULL = 2
    OUTPUT_PUSHPULL = 3
    OUTPUT_OPENDRAIN = 4


class GpioConfig:
    def __init__(self, gpio_id: GpioId, gpio_mode: GpioMode):
        self.gpio_id = gpio_id
        self.gpio_mode = gpio_mode


class OutputData:
    def __init__(self, gpio_id: GpioId, output_data: bool):
        self.gpio_id = gpio_id
        self.output_data = output_data


GpioConfigs = {GpioId[member.name]: GpioMode.INPUT_PULLDOWN for member in GpioId}
GpioData = {GpioId[member.name]: False for member in GpioId}


def encode_gpio_config_msg(config: list) -> bytes:
    global SEQ_NUM, SYNCHRONIZED
    SEQ_NUM += 1
    SYNCHRONIZED = False
    msg = gpio_pb2.GpioMsg()

    # Update configration
    for cfg in config:
        GpioConfigs[cfg.gpio_id] = cfg.gpio_mode

    msg.cfg_msg.gpio0 = GpioConfigs[GpioId.GPIO0].value
    msg.cfg_msg.gpio1 = GpioConfigs[GpioId.GPIO1].value
    msg.cfg_msg.gpio2 = GpioConfigs[GpioId.GPIO2].value
    msg.cfg_msg.gpio3 = GpioConfigs[GpioId.GPIO3].value
    msg.cfg_msg.gpio4 = GpioConfigs[GpioId.GPIO4].value
    msg.cfg_msg.gpio5 = GpioConfigs[GpioId.GPIO5].value
    msg.cfg_msg.gpio6 = GpioConfigs[GpioId.GPIO6].value
    msg.cfg_msg.gpio7 = GpioConfigs[GpioId.GPIO7].value

    msg.sequence_number = SEQ_NUM
    return msg.SerializeToString()


def encode_gpio_data_msg(data: list) -> bytes:
    global SEQ_NUM, SYNCHRONIZED
    SEQ_NUM += 1
    SYNCHRONIZED = False
    msg = gpio_pb2.GpioMsg()

    # Update output state
    for dt in data:
        GpioData[dt.gpio_id] = dt.output_data

    msg.data_msg.gpio0 = GpioData[GpioId.GPIO0]
    msg.data_msg.gpio1 = GpioData[GpioId.GPIO1]
    msg.data_msg.gpio2 = GpioData[GpioId.GPIO2]
    msg.data_msg.gpio3 = GpioData[GpioId.GPIO3]
    msg.data_msg.gpio4 = GpioData[GpioId.GPIO4]
    msg.data_msg.gpio5 = GpioData[GpioId.GPIO5]
    msg.data_msg.gpio6 = GpioData[GpioId.GPIO6]
    msg.data_msg.gpio7 = GpioData[GpioId.GPIO7]
    msg.sequence_number = SEQ_NUM
    return msg.SerializeToString()


def decode_gpio_msg(data: bytes):
    global SEQ_NUM, SYNCHRONIZED, INPUT_DATA
    msg = gpio_pb2.GpioMsg()
    msg.ParseFromString(data)

    inner_msg = msg.WhichOneof("msg")
    # print("Inner msg:", inner_msg)

    if inner_msg == "data_msg":
        if msg.sequence_number >= SEQ_NUM:
            SYNCHRONIZED = True
            print("rx gpio0:", msg.data_msg.gpio0)
            print("rx gpio1:", msg.data_msg.gpio1)
            print("rx gpio2:", msg.data_msg.gpio2)
            print("rx gpio3:", msg.data_msg.gpio3)
            print("rx gpio4:", msg.data_msg.gpio4)
            print("rx gpio5:", msg.data_msg.gpio5)
            print("rx gpio6:", msg.data_msg.gpio6)
            print("rx gpio7:", msg.data_msg.gpio7)

            INPUT_DATA = {
                GpioId.GPIO0: msg.data_msg.gpio0,
                GpioId.GPIO1: msg.data_msg.gpio1,
                GpioId.GPIO2: msg.data_msg.gpio2,
                GpioId.GPIO3: msg.data_msg.gpio3,
                GpioId.GPIO4: msg.data_msg.gpio4,
                GpioId.GPIO5: msg.data_msg.gpio5,
                GpioId.GPIO6: msg.data_msg.gpio6,
                GpioId.GPIO7: msg.data_msg.gpio7,
            }
        else:
            print("Rejected data msg! ==========================#")
