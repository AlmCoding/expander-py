from proto.proto_py import i2c_pb2
from enum import Enum
import tiny_frame as tf


class I2cId(Enum):
    I2C0 = 0
    I2C1 = 1


I2C_INSTANCE = {
    I2cId.I2C0: None,
    I2cId.I2C1: None
}


class I2cMasterRequest:
    def __init__(self, slave_addr: int, write_data: bytes, read_size: int):
        self.pending = True
        self.request_id = None
        self.slave_addr = slave_addr
        self.read_size = read_size
        self.write_data = write_data
        self.read_data = None


class I2cInterface:
    def __init__(self, i2c_id: I2cId, i2c_addr: int, i2c_clock: int):
        self.i2c_id = i2c_id
        self.i2c_addr = i2c_addr
        self.i2c_clock = i2c_clock
        self.sequence_number = 0
        self.request_id_counter = 0
        self.master_queue_space = 8
        self.master_buffer_space = 64
        self.master_requests = {}

        if self.i2c_id == I2cId.I2C0:
            self.i2c_idm = i2c_pb2.I2cId.I2C0
        else:
            self.i2c_idm = i2c_pb2.I2cId.I2C1

        global I2C_INSTANCE
        I2C_INSTANCE[self.i2c_id] = self

    def __del__(self):
        global I2C_INSTANCE
        if I2C_INSTANCE[self.i2c_id] is self:
            I2C_INSTANCE[self.i2c_id] = None

    def can_accept_master_request(self, write_size: int, read_size: int) -> bool:
        return (self.master_queue_space > 0 and
                self.master_buffer_space >= (write_size + read_size))

    def get_pending_master_request_ids(self) -> list:
        return [request.request_id for rid, request in self.master_requests if request.pending]

    def get_completed_master_request_ids(self) -> list:
        return [request.request_id for rid, request in self.master_requests if not request.pending]

    def get_master_request(self, request_id: int, remove_completed=True) -> I2cMasterRequest:
        if request_id not in self.master_requests.keys():
            return None

        request = self.master_requests[request_id]
        if remove_completed and not request.pending:
            del self.master_requests[request_id]

        return request

    def send_config_msg(self) -> None:
        self.sequence_number += 1

        msg = i2c_pb2.I2cMsg()
        msg.i2c_id = self.i2c_idm
        msg.sequence_number = self.sequence_number
        msg.cfg_msg.clock_rate = self.i2c_clock

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_I2C.value, msg_bytes, 0)

    def send_master_request_msg(self, request: I2cMasterRequest) -> int:
        self.sequence_number += 1
        self.request_id_counter += 1

        request.pending = True
        request.request_id = self.request_id_counter
        request.read_data = None
        self.master_requests[request.request_id] = request

        msg = i2c_pb2.I2cMsg()
        msg.i2c_id = self.i2c_idm
        msg.sequence_number = self.sequence_number
        msg.data_msg.request_id = request.request_id
        msg.data_msg.slave_addr = request.slave_addr
        msg.data_msg.read_size = request.read_size
        msg.data_msg.data = request.write_data

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_I2C.value, msg_bytes, 0)
        return request.request_id

    def receive_msg_cb(self, msg: i2c_pb2.I2cMsg) -> None:
        inner_msg = msg.WhichOneof("msg")

        if inner_msg == "data_msg":
            request_id = msg.data_msg.request_id
            self.master_requests[request_id].read_data = msg.data_msg.data
            self.master_requests[request_id].pending = False

        elif inner_msg == "status_msg":
            if msg.sequence_number >= self.sequence_number:
                self.master_queue_space = msg.status_msg.master_queue_space
                self.master_buffer_space = msg.status_msg.master_buffer_space

        else:
            print("Rejected I2C msg! ==========================#")


def receive_i2c_msg_cb(_, tf_msg: tf.TF.TF_Msg) -> None:
    global I2C_INSTANCE
    msg = i2c_pb2.I2cMsg()
    msg.ParseFromString(bytes(tf_msg.data))

    if msg.i2c_id == i2c_pb2.I2cId.I2C0:
        instance = I2C_INSTANCE[I2cId.I2C0]
    else:
        instance = I2C_INSTANCE[I2cId.I2C1]

    if instance:
        instance.receive_msg_cb(msg)


tf.tf_register_callback(tf.TfMsgType.TYPE_I2C, receive_i2c_msg_cb)
