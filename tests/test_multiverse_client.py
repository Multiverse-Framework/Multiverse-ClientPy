import unittest
import subprocess
import os
import time
import logging
import sys
from typing import List, Dict, Any
import numpy

handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

from multiverse_client_py import MultiverseClient, MultiverseMetaData


class MultiverseConnector(MultiverseClient):
    def __init__(self, port: str, multiverse_meta_data: MultiverseMetaData, transport: str = "Tcp") -> None:
        if transport == "Tcp":
            self._transport = "Tcp"
            self._host = "127.0.0.1"
            self._server_port = "7000"
        elif transport == "Udp":
            self._transport = "Udp"
            self._host = "127.0.0.1"
            self._server_port = "8000"
        elif transport == "Zmq":
            self._transport = "Zmq"
            self._host = "tcp://127.0.0.1"
            self._server_port = "9000"
        else:
            raise ValueError("Unknown transport {}".format(transport))
        super().__init__(port, multiverse_meta_data)

    def loginfo(self, message: str) -> None:
        logger.info(message)

    def logwarn(self, message: str) -> None:
        logger.warning(message)

    def _run(self) -> None:
        self.loginfo("Start running the client.")
        self._connect_and_start()

    def send_and_receive_meta_data(self) -> None:
        self.loginfo("Sending request meta data: " + str(self.request_meta_data))
        self._communicate(True)
        self.loginfo("Received response meta data: " + str(self.response_meta_data))

    def send_and_receive_data(self) -> None:
        self.loginfo("Sending data: " + str(self.send_data))
        self._communicate(False)
        self.loginfo("Received data: " + str(self.receive_data))


multiverse_server_cpp_path = os.path.join(os.path.dirname(__file__), "multiverse_server_cpp")
multiverse_server_rust_path = os.path.join(os.path.dirname(__file__), "multiverse_server_rust")

multiverse_meta_data_dict = {
    "send": {
        "Tcp": [],
        "Udp": [],
        "Zmq": [],
    },
    "receive": {
        "Tcp": [],
        "Udp": [],
        "Zmq": [],
    },
}
object_names = [f"object_{i}" for i in range(10)]
attributes = {
    "position": [0.0] * 3,
    "quaternion": [0.0] * 4,
    "joint_angular_position": [0.0],
    "cmd_joint_angular_position": [0.0],
}

def get_random_request_meta_data(enable_receive: bool = False) -> Dict[str, Any]:
    request_meta_data = {
        "send": {},
        "receive": {},
    }
    send_count = numpy.random.randint(1, 10)
    for i in range(send_count):
        send_attribute_count = numpy.random.randint(1, len(attributes))
        send_attribute_names = numpy.random.choice(list(attributes.keys()), send_attribute_count, replace=False)
        request_meta_data["send"][object_names[i]] = send_attribute_names.tolist()
    if enable_receive:
        receive_count = numpy.random.randint(1, 10)
        for i in range(receive_count):
            receive_attribute_count = numpy.random.randint(1, len(attributes))
            receive_attribute_names = numpy.random.choice(list(attributes.keys()), receive_attribute_count, replace=False)
            request_meta_data["receive"][object_names[i]] = receive_attribute_names.tolist()
    return request_meta_data

for n in range(10):
    for i, transport in enumerate(["Tcp", "Udp", "Zmq"]):
        multiverse_meta_data_dict["send"][transport].append((
            MultiverseMetaData(
                world_name="world",
                simulation_name=f"send_{transport}_{n}",
                length_unit="m",
                angle_unit="rad",
                mass_unit="kg",
                time_unit="s",
                handedness="rhs",
            ),
            f"{5000 + 6 * n + i}"
        ))
        multiverse_meta_data_dict["receive"][transport].append((
            MultiverseMetaData(
                world_name="world",
                simulation_name=f"receive_{transport}_{n}",
                length_unit="m",
                angle_unit="rad",
                mass_unit="kg",
                time_unit="s",
                handedness="rhs",
            ),
            f"{5000 + 6 * n + i + 1}"
        ))

def create_multiverse_clients(n_clients: int = 1, transport_type: str="Tcp") -> List[MultiverseConnector]:
    multiverse_connectors = []
    for client_id in range(n_clients):
        multiverse_meta_data, port = multiverse_meta_data_dict["send"][transport_type][client_id]
        multiverse_connector = MultiverseConnector(port=port, multiverse_meta_data=multiverse_meta_data,
                                                   transport=transport_type)
        multiverse_connector.run()
        multiverse_connectors.append(multiverse_connector)
    return multiverse_connectors

class MultiverseClientTestCase(unittest.TestCase):
    multiverse_server_path = multiverse_server_cpp_path
    multiverse_server_process = None
    multiverse_connector = None

    @classmethod
    def setUpClass(cls):
        logger.info(f"Starting multiverse_server on {cls.multiverse_server_path}")
        cls.multiverse_server_process = subprocess.Popen(
            [cls.multiverse_server_path,
             "--transport", "tcp", "--bind", "127.0.0.1:7000",
             "--transport", "udp", "--bind", "127.0.0.1:8000",
             "--transport", "zmq", "--bind", "tcp://*:9000", ])
        logger.info(f"multiverse_server started on {cls.multiverse_server_path}")
        time.sleep(0.5) # TODO: Remove

    @classmethod
    def tearDownClass(cls):
        logger.info(f"Stopping multiverse_server on {cls.multiverse_server_path}")
        cls.multiverse_server_process.kill()
        logger.info(f"multiverse_server stopped on {cls.multiverse_server_path}")

    def test_multiverse_server(self):
        start_time = time.time()
        self.assertTrue(self.multiverse_server_process.poll() is None)
        time.sleep(1.0)
        self.assertTrue(self.multiverse_server_process.poll() is None)
        self.assertLess(time.time() - start_time, 5.0)

    def test_multiverse_client_tcp_connect(self, n_clients=1):
        start_time = time.time()
        multiverse_connectors = create_multiverse_clients(n_clients=n_clients, transport_type="Tcp")
        time.sleep(1.0)
        for multiverse_connector in multiverse_connectors:
            multiverse_connector.stop()
        self.assertLess(time.time() - start_time, 5.0)

    def test_multiverse_client_udp_connect(self, n_clients=1):
        start_time = time.time()
        multiverse_connectors = create_multiverse_clients(n_clients=n_clients, transport_type="Udp")
        time.sleep(1.0)
        for multiverse_connector in multiverse_connectors:
            multiverse_connector.stop()
        self.assertLess(time.time() - start_time, 5.0)

    def test_multiverse_client_zmq_connect(self, n_clients=1):
        start_time = time.time()
        multiverse_connectors = create_multiverse_clients(n_clients=n_clients, transport_type="Zmq")
        time.sleep(1.0)
        for multiverse_connector in multiverse_connectors:
            multiverse_connector.stop()
        self.assertLess(time.time() - start_time, 5.0)

    def check_multiverse_client_send_request_meta_data(self, multiverse_connectors: List[MultiverseConnector]):
        start_time = time.time()
        for multiverse_connector in multiverse_connectors:
            multiverse_connector.request_meta_data.update(get_random_request_meta_data())
            multiverse_connector.send_and_receive_meta_data()
        time.sleep(1.0)
        for multiverse_connector in multiverse_connectors:
            while "send" not in multiverse_connector.response_meta_data:
                self.multiverse_connector.loginfo("Waiting for send response meta data.")
                time.sleep(0.01)
            send_objects = multiverse_connector.response_meta_data["send"]
            self.assertEqual(len(send_objects), len(multiverse_connector.request_meta_data["send"]))
            for object_name, send_attributes in send_objects.items():
                self.assertEqual(len(send_attributes), len(multiverse_connector.request_meta_data["send"][object_name]))
        for multiverse_connector in multiverse_connectors:
            multiverse_connector.stop()
        self.assertLess(time.time() - start_time, 5.0)

    def test_multiverse_client_tcp_send_request_meta_data(self, n_clients=1):
        multiverse_connectors = create_multiverse_clients(n_clients=n_clients, transport_type="Tcp")
        self.check_multiverse_client_send_request_meta_data(multiverse_connectors)

    def test_multiverse_client_udp_send_request_meta_data(self, n_clients=1):
        multiverse_connectors = create_multiverse_clients(n_clients=n_clients, transport_type="Udp")
        self.check_multiverse_client_send_request_meta_data(multiverse_connectors)

    def test_multiverse_client_zmq_send_request_meta_data(self, n_clients=1):
        multiverse_connectors = create_multiverse_clients(n_clients=n_clients, transport_type="Zmq")
        self.check_multiverse_client_send_request_meta_data(multiverse_connectors)


if __name__ == '__main__':
    unittest.main()
