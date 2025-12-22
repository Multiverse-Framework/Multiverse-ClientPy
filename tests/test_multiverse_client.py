import unittest
import subprocess
import os
import time
import logging
import sys
from typing import List

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

def create_multiverse_clients(n_clients: int = 1, transport_type: str="Tcp") -> List[MultiverseClient]:
    multiverse_connectors = []
    for client_id in range(n_clients):
        multiverse_meta_data, port = multiverse_meta_data_dict["send"][transport_type][client_id]
        multiverse_connector = MultiverseConnector(port=port, multiverse_meta_data=multiverse_meta_data,
                                                   transport=transport_type)
        multiverse_connector.run()
        multiverse_connectors.append(multiverse_connector)
    return multiverse_connectors

class MultiverseClientTestCase(unittest.TestCase):
    multiverse_server_path = multiverse_server_rust_path
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
        self.assertAlmostEqual(time.time() - start_time, 1.0, places=2)

    def test_multiverse_client_tcp_connect(self, n_clients=1):
        start_time = time.time()
        multiverse_connectors = create_multiverse_clients(n_clients=n_clients, transport_type="Tcp")
        time.sleep(1.0)
        for multiverse_connector in multiverse_connectors:
            multiverse_connector.stop()
        self.assertAlmostEqual(time.time() - start_time, 1.0, places=2)

    def test_multiverse_client_udp_connect(self, n_clients=1):
        start_time = time.time()
        multiverse_connectors = create_multiverse_clients(n_clients=n_clients, transport_type="Udp")
        time.sleep(1.0)
        for multiverse_connector in multiverse_connectors:
            multiverse_connector.stop()
        self.assertAlmostEqual(time.time() - start_time, 1.0, places=2)

    def test_multiverse_client_zmq_connect(self, n_clients=1):
        start_time = time.time()
        multiverse_connectors = create_multiverse_clients(n_clients=n_clients, transport_type="Zmq")
        time.sleep(1.0)
        for multiverse_connector in multiverse_connectors:
            multiverse_connector.stop()
        self.assertAlmostEqual(time.time() - start_time, 1.0, places=2)


if __name__ == '__main__':
    unittest.main()
