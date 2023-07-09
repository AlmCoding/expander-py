from proto.proto_py import uart_pb2
from enum import Enum

RX_BUFFER = bytearray()
TX_COMPLETE = True
TX_SPACE = 64
SEQ_NUM = 0


class UartId(Enum):
    UART1 = 0
    UART2 = 1


def encode_uart_config_msg(uart_id: UartId, baud_rate: int) -> bytes:
    global SEQ_NUM
    SEQ_NUM += 1
    msg = uart_pb2.UartMsg()

    if uart_id == UartId.UART1:
        msg.cfg_msg.id = uart_pb2.UartId.UART1
    else:
        msg.cfg_msg.id = uart_pb2.UartId.UART2

    msg.cfg_msg.baudrate = baud_rate
    msg.sequence_number = SEQ_NUM
    return msg.SerializeToString()


def encode_uart_data_msg(uart_id: UartId, data: bytes) -> bytes:
    global SEQ_NUM
    SEQ_NUM += 1
    msg = uart_pb2.UartMsg()

    if uart_id == UartId.UART1:
        msg.data_msg.id = uart_pb2.UartId.UART1
    else:
        msg.data_msg.id = uart_pb2.UartId.UART2

    msg.data_msg.data = data
    msg.sequence_number = SEQ_NUM
    return msg.SerializeToString()


def decode_uart_msg(data: bytes):
    global SEQ_NUM
    msg = uart_pb2.UartMsg()
    msg.ParseFromString(data)

    inner_msg = msg.WhichOneof("msg")
    # print("Inner msg:", inner_msg)

    if inner_msg == "data_msg":
        global RX_BUFFER
        RX_BUFFER += msg.data_msg.data
    elif inner_msg == "status_msg":
        global TX_COMPLETE, TX_SPACE
        if msg.sequence_number >= SEQ_NUM:
            TX_COMPLETE = msg.status_msg.tx_complete
            TX_SPACE = msg.status_msg.tx_space
            print("Status: tx_complete {}, tx_space {}, tx_overflow {}, seq_num {}"
                  .format(msg.status_msg.tx_complete, msg.status_msg.tx_space,
                          msg.status_msg.tx_overflow, msg.sequence_number))
            if msg.status_msg.tx_overflow:
                raise Exception("Tx overflow!")
    else:
        print("Rejected status msg! ==========================#")
