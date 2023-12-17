from proto.proto_py import gpio_pb2
from enum import Enum
import msg.tiny_frame as tf


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


class GpioInterface:
    SequenceNumber = 0
    Config = {GpioId[member.name]: GpioMode.INPUT_PULLDOWN for member in GpioId}
    Data = {GpioId[member.name]: False for member in GpioId}
    Synchronized = True
    InputData = None

    @staticmethod
    def send_config_msg(config: list) -> None:
        GpioInterface.SequenceNumber += 1
        GpioInterface.Synchronized = False

        # Update configration
        for cfg in config:
            GpioInterface.Config[cfg.gpio_id] = cfg.gpio_mode

        msg = gpio_pb2.GpioMsg()
        msg.sequence_number = GpioInterface.SequenceNumber
        msg.cfg.gpio0 = GpioInterface.Config[GpioId.GPIO0].value
        msg.cfg.gpio1 = GpioInterface.Config[GpioId.GPIO1].value
        msg.cfg.gpio2 = GpioInterface.Config[GpioId.GPIO2].value
        msg.cfg.gpio3 = GpioInterface.Config[GpioId.GPIO3].value
        msg.cfg.gpio4 = GpioInterface.Config[GpioId.GPIO4].value
        msg.cfg.gpio5 = GpioInterface.Config[GpioId.GPIO5].value
        msg.cfg.gpio6 = GpioInterface.Config[GpioId.GPIO6].value
        msg.cfg.gpio7 = GpioInterface.Config[GpioId.GPIO7].value

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_GPIO.value, msg_bytes, 0)

    @staticmethod
    def send_data_msg(data: list) -> None:
        GpioInterface.SequenceNumber += 1
        GpioInterface.Synchronized = False

        # Update output state
        for dt in data:
            GpioInterface.Data[dt.gpio_id] = dt.output_data

        msg = gpio_pb2.GpioMsg()
        msg.sequence_number = GpioInterface.SequenceNumber
        msg.data.gpio0 = GpioInterface.Data[GpioId.GPIO0]
        msg.data.gpio1 = GpioInterface.Data[GpioId.GPIO1]
        msg.data.gpio2 = GpioInterface.Data[GpioId.GPIO2]
        msg.data.gpio3 = GpioInterface.Data[GpioId.GPIO3]
        msg.data.gpio4 = GpioInterface.Data[GpioId.GPIO4]
        msg.data.gpio5 = GpioInterface.Data[GpioId.GPIO5]
        msg.data.gpio6 = GpioInterface.Data[GpioId.GPIO6]
        msg.data.gpio7 = GpioInterface.Data[GpioId.GPIO7]

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_GPIO.value, msg_bytes, 0)

    @staticmethod
    def receive_msg_cb(msg: gpio_pb2.GpioMsg):
        if msg.sequence_number < GpioInterface.SequenceNumber:
            print("Rejected GPIO msg! ==========================#")
            return

        inner_msg = msg.WhichOneof("msg")
        if inner_msg == "data":
            GpioInterface.Synchronized = True
            print("rx gpio0:", msg.data.gpio0)
            print("rx gpio1:", msg.data.gpio1)
            print("rx gpio2:", msg.data.gpio2)
            print("rx gpio3:", msg.data.gpio3)
            print("rx gpio4:", msg.data.gpio4)
            print("rx gpio5:", msg.data.gpio5)
            print("rx gpio6:", msg.data.gpio6)
            print("rx gpio7:", msg.data.gpio7)

            GpioInterface.InputData = {
                GpioId.GPIO0: msg.data.gpio0,
                GpioId.GPIO1: msg.data.gpio1,
                GpioId.GPIO2: msg.data.gpio2,
                GpioId.GPIO3: msg.data.gpio3,
                GpioId.GPIO4: msg.data.gpio4,
                GpioId.GPIO5: msg.data.gpio5,
                GpioId.GPIO6: msg.data.gpio6,
                GpioId.GPIO7: msg.data.gpio7,
            }


def receive_gpio_msg_cb(_, tf_msg: tf.TF.TF_Msg) -> None:
    msg = gpio_pb2.GpioMsg()
    msg.ParseFromString(bytes(tf_msg.data))
    GpioInterface.receive_msg_cb(msg)


tf.tf_register_callback(tf.TfMsgType.TYPE_GPIO, receive_gpio_msg_cb)
