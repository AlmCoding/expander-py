from proto.proto_py import uart_pb2
from enum import Enum
import tiny_frame as tf

UART_TX_BUFFER_SPACE = 64


class UartId(Enum):
    UART0 = 0
    UART1 = 1


UART_INSTANCE = {
    UartId.UART0: None,
    UartId.UART1: None
}


class UartInterface:
    def __init__(self, uart_id: UartId, baud_rate: int):
        self.uart_id = uart_id
        self.uart_baud = baud_rate
        self.sequence_number = 0
        self.tx_buffer_space = UART_TX_BUFFER_SPACE
        self.tx_buffer_empty = True
        self.rx_buffer = bytearray()

        if self.uart_id == UartId.UART0:
            self.uart_idm = uart_pb2.UartId.UART0
        else:
            self.uart_idm = uart_pb2.UartId.UART0

        global UART_INSTANCE
        UART_INSTANCE[self.uart_id] = self

    def __del__(self):
        global UART_INSTANCE
        if UART_INSTANCE[self.uart_id] is self:
            UART_INSTANCE[self.uart_id] = None

    def can_accept_request(self, tx_size: int):
        return self.tx_buffer_space >= tx_size

    def send_config_msg(self) -> None:
        self.sequence_number += 1

        msg = uart_pb2.UartMsg()
        msg.uart_id = self.uart_idm
        msg.sequence_number = self.sequence_number
        msg.cfg.baud_rate = self.uart_baud

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_UART.value, msg_bytes, 0)

    def send_data_msg(self, data: bytes) -> None:
        self.sequence_number += 1
        self.tx_buffer_space -= len(data)
        self.tx_buffer_empty = False

        msg = uart_pb2.UartMsg()
        msg.uart_id = self.uart_idm
        msg.sequence_number = self.sequence_number
        msg.data.data = data

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_UART.value, msg_bytes, 0)

    def receive_msg_cb(self, msg: uart_pb2.UartMsg):
        inner_msg = msg.WhichOneof("msg")

        if inner_msg == "data":
            self.rx_buffer += msg.data.data
        elif inner_msg == "status":
            if msg.sequence_number >= self.sequence_number:
                self.tx_buffer_space = msg.status.tx_space
                self.tx_buffer_empty = msg.status.tx_complete

                print("Status: tx_complete {}, tx_space {}, tx_overflow {}, seq_num {}"
                      .format(msg.status.tx_complete, msg.status.tx_space,
                              msg.status.tx_overflow, msg.sequence_number))
                if msg.status.tx_overflow:
                    raise Exception("Tx overflow!")
        else:
            print("Rejected UART msg! ==========================#")


def receive_uart_msg_cb(_, tf_msg: tf.TF.TF_Msg) -> None:
    global UART_INSTANCE
    msg = uart_pb2.UartMsg()
    msg.ParseFromString(bytes(tf_msg.data))

    if msg.uart_id == uart_pb2.UartId.UART0:
        instance = UART_INSTANCE[UartId.UART0]
    else:
        instance = UART_INSTANCE[UartId.UART1]

    if instance:
        instance.receive_msg_cb(msg)


tf.tf_register_callback(tf.TfMsgType.TYPE_UART, receive_uart_msg_cb)
