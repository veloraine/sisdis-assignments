import logging
import random
import sys
import threading
import time
import traceback
from argparse import ArgumentParser
import socket
from ast import literal_eval
from pprint import pformat
import copy

# import node_socket taken from assignment 1
from node_socket import UdpSocket

def sending_procedure(heartbeat_duration, node_id, neighbors_port, node_ports):
    """
    TODO: complete the sending_procedure
    :param heartbeat_duration: heartbeat duration
    :param node_id: node id
    :param neighbors_port: a list of neighbors port
    :param node_ports: a dictionary with the node's port as the key and its id as the value
    :global status_dictionary: status dictionary
    :global logger: use this to print the answer
    """

    # Heartbeat procedure
    while True:
        time.sleep(heartbeat_duration)
        status_dictionary[f"node-{node_id}"][0] += 1
        logger.info(f"Increase heartbeat node-{node_id}:\n{pformat(status_dictionary)}")

        # Gossip procedure

        # Choose random neighbors
        logger.info("Determining which node to send...")
        random_neighbors = random.sample(neighbors_port, neighbors_to_choose)

        # Get node id from port
        random_neighbors_id = []
        for neighbor in random_neighbors:
            random_neighbors_id.append(f"node-{node_ports[neighbor]}")

        # Send message to random neighbors
        logger.info(f"Send messages to {' and '.join(random_neighbors_id)}")
        
        for neighbor in random_neighbors:
            UdpSocket.send(f"node-{node_id}~{status_dictionary}", neighbor)


def listening_procedure(port, node_id, fault_duration):
    """
    TODO: complete the listening/receiving procedure
    :param port: the port of the node
    :param node_id: node id
    :param fault_duration: duration to assume that a node is a fault
    :global status_dictionary: status dictionary
    :global logger: use this to print the answer
    """

    # Initialize socket
    logger.info("Initiating socket...")
    udp_socket = UdpSocket(port)

    # Listen to all incoming messages
    while True:

        # Receive message
        message = udp_socket.listen()
        sender, content = message[0].split("~")
        content_dict = literal_eval(content)

        logger.info(f"Receive message from {sender}...")
        logger.info(f"Incoming message:\n{pformat(content_dict)}")

        # Update status dictionary
        for key, value in content_dict.items():
            if value[0] > status_dictionary[key][0]:
                status_dictionary[key] = value

        # initialize dead thread checker, one for each node
        thread = threading.Thread(target=check_dead_single_node, args=(fault_duration, sender))
        thread.name = f"dead_thread_{sender}"
        logger.info(f"Thread {thread.name} started")
        thread.start()

def check_dead_single_node(fault_duration, node_id):
    # every single nodes have its own dead checker

    initial_status = status_dictionary[node_id][0]
    time.sleep(fault_duration)
    if initial_status == status_dictionary[node_id][0]:
        status_dictionary[node_id][1] = False
        logger.info(f"This node become a fault: {node_id}")
        logger.info(f"Node fault status_dictionary:\n{pformat(status_dictionary)}")

def thread_exception_handler(args):
    logger.error(f"Uncaught exception", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

def reload_logging_windows(filename):
    log = logging.getLogger()
    for handler in log.handlers:
        log.removeHandler(handler)
    logging.basicConfig(format='%(asctime)-4s %(levelname)-6s %(threadName)s:%(lineno)-3d %(message)s',
                        datefmt='%H:%M:%S',
                        filename=filename,
                        filemode='w',
                        level=logging.INFO)

def main(heartbeat_duration=1, num_of_neighbors_to_choose=1,
         fault_duration=1, port=1000, node_id=1, neighbors_ports=(1000,)):
    reload_logging_windows(f"logs/node{node_id}.txt")
    global logger
    logger = logging.getLogger(__name__)

    # make num_of_neighbors_to_choose a global variable
    global neighbors_to_choose
    neighbors_to_choose = num_of_neighbors_to_choose

    try:
        logger.info(f"Node with id {node_id} is running...")
        logger.debug(f"heartbeat_duration: {heartbeat_duration}")
        logger.debug(f"fault_duration: {fault_duration}")
        logger.debug(f"port: {port}")
        logger.debug(f"num_of_neighbors_to_choose: {num_of_neighbors_to_choose}")
        logger.debug(f"neighbors_ports: {neighbors_ports}")

        

        logger.info("Configure the status_dictionary global variable...")
        global status_dictionary
        status_dictionary = {}
        node_ports = {}
        for i in range(len(neighbors_ports)):
            status_dictionary[f"node-{i + 1}"] = [0, True]
            node_ports[neighbors_ports[i]] = i+1

            # initialize dead thread checker, one for each node
            thread = threading.Thread(target=check_dead_single_node, args=(fault_duration, f"node-{i + 1}"))
            thread.name = f"dead_thread_{i+1}"
            thread.start()
            logger.info(f"Thread {thread.name} started")

        neighbors_ports.remove(port)
        logger.info(f"status_dictionary:\n{pformat(status_dictionary)}")
        logger.info("Done configuring the status_dictionary...")

        logger.info("Executing the listening procedure...")
        threading.excepthook = thread_exception_handler
        thread = threading.Thread(target=listening_procedure, args=(port, node_id, fault_duration))
        thread.name = "listening_thread"
        thread.start()
        logger.info("Executing the sending procedure...")
        thread = threading.Thread(target=sending_procedure,
                         args=(heartbeat_duration,
                               node_id, neighbors_ports, node_ports))
        thread.name = "sending_thread"
        thread.start()

    except Exception as e:
        logger.exception("Caught Error")
        raise



if __name__ == '__main__':
    main()