import logging
import threading
import socket
import json
import random


def thread_exception_handler(args):
    logging.error(f"Uncaught exception", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


class Raft:

    def __init__(self, node_id: int, port: int, neighbors_ports: list, lb_fault_duration: int, is_continue: bool,
                 heartbeat_duration: float):
        self.heartbeat_duration = heartbeat_duration
        self.is_continue = is_continue
        self.lb_fault_duration = lb_fault_duration
        self.neighbors_ports = neighbors_ports
        self.port = port
        self.node_id = node_id

    def start(self):
        # Setup socket for sending and receiving messages
        self.socket = UdpSocket(self.port)

        # Check if the node is recovering from crash or new node
        if self.is_continue:
            logging.info("Recovering from crash")
            self.recovery_from_crash()
        else:
            logging.info("Initializing node")
            self.initialize()

        # start election timer
        self.start_election_timer()

        # listen to incoming messages
        logging.info("Listen for any inputs...")
        while True:
            msg, sender = self.socket.listen()
            if msg["type"] == MessageType.VOTE_REQUEST:
                logging.info(f"node{msg['node_id']} sends a vote_request")
                self.on_vote_request(msg)
            elif msg["type"] == MessageType.VOTE_RESPONSE:
                self.on_vote_response(msg)
            elif msg["type"] == MessageType.HEARTBEAT:
                logging.info(f"node{msg['node_id']} sends a log_request")
                self.on_heartbeat(msg)
        
    def initialize(self):
        # initialize node state
        self.current_term = 0
        self.voted_for = None
        self.log = []
        self.commit_length = 0
        self.current_role = NodeStates.FOLLOWER
        self.current_leader = None
        self.votes_received = []
        self.sent_length = {}
        self.acked_length = {}

    def recovery_from_crash(self):
        # recover node state, load from file
        self.load_state()
        self.current_role = NodeStates.FOLLOWER
        self.current_leader = None
        self.votes_received = []
        self.sent_length = {}
        self.acked_length = {}

    def on_suspect_leader_failure_or_timeout(self):
        # if leader is suspected to be failed or election timeout
        logging.info("Leader is suspected to be failed")
        self.current_term += 1
        self.current_role = NodeStates.CANDIDATE
        self.voted_for = self.node_id
        self.votes_received = [self.node_id]

        # to initialize var
        self.last_term = 0

        if len(self.log) > 0:
            # get last log index and term
            last_log_index = len(self.log) - 1
            self.last_term = self.log[last_log_index].term

        msg = {"type": MessageType.VOTE_REQUEST, 
                "current_term": self.current_term, 
                "log_length": len(self.log), 
                "node_id": self.node_id, 
                "last_term": self.last_term,}
        
        # send vote_request to all neighbors
        for neighbor_port in self.neighbors_ports:
            if neighbor_port == self.port:
                continue
            self.socket.send(msg, neighbor_port)
        
        self.save_state()
        
        self.reset_election_timer()

    def on_vote_request(self, msg):
        # if receive vote_request from candidate
        logging.info("vote procedure is starting...")
        if msg["current_term"] > self.current_term:
            logging.info(f"Candidate node {msg['node_id']} has higher term than my term")
            logging.info(f"Change term from {self.current_term} to {msg['current_term']}")
            self.current_term = msg["current_term"]
            self.current_role = "follower"
            self.voted_for = None

        self.last_term = 0
        if len(self.log) > 0:
            # get last log index and term
            last_log_index = len(self.log) - 1
            self.last_term = self.log[last_log_index].term

        # check if the candidate's log is up-to-date
        log_ok = msg["last_term"] > self.last_term or (msg["last_term"] == self.last_term and msg["log_length"] >= len(self.log))
        
        # check condition for voting
        if msg["current_term"] == self.current_term and log_ok and self.voted_for in [None, msg["node_id"]]:
            self.voted_for = msg["node_id"]
            msg = {"type": MessageType.VOTE_RESPONSE, 
                    "current_term": self.current_term, 
                    "node_id": self.node_id, 
                    "vote_granted": True}
            logging.info(f"I vote for canidate node {self.voted_for}")
            self.socket.send(msg, self.neighbors_ports[self.voted_for - 1])

        else:
            msg = {"type": MessageType.VOTE_RESPONSE, 
                    "current_term": self.current_term, 
                    "node_id": self.node_id, 
                    "vote_granted": False}
            self.socket.send(msg, self.neighbors_ports[self.voted_for - 1])

        logging.info(f"Connection for vote_procedure from candidate {self.voted_for} has been closed...")
    
    def on_vote_response(self, msg):
        # if receive vote_response from candidate
        if self.current_role == NodeStates.CANDIDATE and msg["current_term"] == self.current_term and msg["vote_granted"]:
            logging.info(f"Received vote response from {msg['node_id']}")
            self.votes_received.append(msg["node_id"])
            logging.info(f"Votes received: {self.votes_received}")

            if len(self.votes_received) > (len(self.neighbors_ports) + 1) / 2:
                # if received votes from majority of nodes
                logging.info(f"Node-{self.node_id} elected as leader")
                self.current_role = NodeStates.LEADER
                self.current_leader = self.node_id

                self.cancel_election_timer()
                
                # start heartbeat thread
                self.send_heartbeat()

                for neighbor_port in self.neighbors_ports:
                    self.sent_length[neighbor_port] = len(self.log)
                    self.acked_length[neighbor_port] = 0
                    # TODO: replicate log (?)

        
        elif msg["current_term"] > self.current_term:
            self.current_term = msg["current_term"]
            self.current_role = NodeStates.FOLLOWER
            self.voted_for = None

            self.reset_election_timer()

    def send_heartbeat(self):
        # send heartbeat to all neighbors to say that leader is alive
        if self.current_role != NodeStates.LEADER:
            return
        
        msg = {"type": MessageType.HEARTBEAT, 
                "current_term": self.current_term, 
                "node_id": self.node_id}
        for neighbor_port in self.neighbors_ports:
            if neighbor_port == self.port:
                continue
            self.socket.send(msg, neighbor_port)
            logging.info(f"Sending heartbeat message to node {neighbor_port}...")

        self.heartbeat_thread = threading.Timer(self.heartbeat_duration, self.send_heartbeat)
        self.heartbeat_thread.start()

    def on_heartbeat(self, msg):
        # if receive heartbeat from leader
        if self.current_role == NodeStates.LEADER:
            return
        
        logging.info("Receive log is starting...")

        if msg["current_term"] > self.current_term:
            self.current_term = msg["current_term"]
            self.voted_for = None

        if msg["current_term"] == self.current_term:
            self.current_role = NodeStates.FOLLOWER
            self.current_leader = msg["node_id"]

        self.save_state()
        self.reset_election_timer()
        
        # log_ok etc

    def save_state(self):
        # save state to file
        logging.info("Saving state")
        with open(f"persistent/node{self.node_id}.txt", "w") as f:
            f.write(f"{self.current_term}\n{self.voted_for}\n{self.log}\n{self.commit_length}\n")

    def load_state(self):
        # load state from file
        logging.info("Loading state")
        with open(f"persistent/node{self.node_id}.txt", "r") as f:
            self.current_term = int(f.readline())
            self.voted_for = int(f.readline())
            self.log = eval(f.readline())
            self.commit_length = int(f.readline())
                    
    def start_election_timer(self):
        logging.info("Election timer will start...")
        random_time = random.uniform(self.lb_fault_duration, self.lb_fault_duration + 4)
        logging.info(f"Election timer duration: {round(random_time, 1)}s")
        self.election_timer = threading.Timer(random_time, self.on_suspect_leader_failure_or_timeout)
        self.election_timer.start()

    def reset_election_timer(self):
        self.cancel_election_timer()
        self.start_election_timer()

    def cancel_election_timer(self):
        logging.info("stop election timer...")
        self.election_timer.cancel()

def reload_logging_windows(filename):
    log = logging.getLogger()
    for handler in log.handlers:
        log.removeHandler(handler)
    logging.basicConfig(format='%(asctime)-4s %(levelname)-6s %(threadName)s:%(lineno)-3d %(message)s',
                        datefmt='%H:%M:%S',
                        filename=filename,
                        filemode='w',
                        level=logging.INFO)

def main(heartbeat_duration=1, lb_fault_duration=1, port=1000,
         node_id=1, neighbors_ports=(1000,), is_continue=False):
    reload_logging_windows(f"logs/node{node_id}.txt")
    threading.excepthook = thread_exception_handler
    try:
        logging.info(f"Node with id {node_id} is running...")
        logging.debug(f"heartbeat_duration: {heartbeat_duration}")
        logging.debug(f"lower_bound_fault_duration: {lb_fault_duration}")
        logging.debug(f"upper_bound_fault_duration = {lb_fault_duration}s + 4s")
        logging.debug(f"port: {port}")
        logging.debug(f"neighbors_ports: {neighbors_ports}")
        logging.debug(f"is_continue: {is_continue}")

        logging.info("Create raft object...")
        raft = Raft(node_id, port, neighbors_ports, lb_fault_duration, is_continue, heartbeat_duration)

        logging.info("Execute raft.start()...")
        raft.start()
    except Exception:
        logging.exception("Caught Error")
        raise

# imported from previous assignment
class NodeSocket:

    def __init__(self, socket_kind: socket.SocketKind, port: int = 0):
        sc = socket.socket(socket.AF_INET, socket_kind)
        sc.bind(('127.0.0.1', port))
        self.sc = sc

class UdpSocket(NodeSocket):

    def __init__(self, port: int = 0):
        super(UdpSocket, self).__init__(socket.SOCK_DGRAM, port)

    def listen(self):
        input_value_byte, address = self.sc.recvfrom(1024)
        response = json.loads(input_value_byte.decode("UTF-8"))
        return response, address

    @staticmethod
    def send(message: dict, port: int = 0):
        message = json.dumps(message)
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.sendto(message.encode("UTF-8"), ("127.0.0.1", port))
        client_socket.close()

class NodeStates:
    LEADER = 1
    FOLLOWER = 2
    CANDIDATE = 3


class MessageType:
    VOTE_REQUEST = 1
    VOTE_RESPONSE = 2
    HEARTBEAT = 3
