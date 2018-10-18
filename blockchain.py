# -*- coding: utf-8 -*-
"""
Created on Thu Sep 28 14:47:51 2017

@author: hha
"""
import hashlib
import json
from time import time
from uuid import uuid4

from flask import Flask, jsonify, request
from urllib.parse import urlparse

import requests

class Blockchain (object): 
    def __init__(self):
        self.chain = []
        self.current_transaction = []
        self.nodes = set()

        # Create genesis block
        self.new_block (previous_hash = 1, proof = 100)

    def register_node (self, address: str) -> None:
        parsed_url = urlparse (address)
        self.nodes.add(parsed_url.netloc)

    def new_block(self, proofi: int, previous_hash Optional[str]) -> Dict [str,
                                                                           Any]:
        """
        param: proof <int> the proof given by the Proof of Work alg
               previous_hash <str> (Optional) Hash of previous block
        return: <dict> new block
        """
        block = {
                'index': len (self.chain) + 1,
                'timestamp': time(),
                'transaction':self.current_transaction,
                'proof':proof,
                'previous_hash':previous_hash or self.hash(self.chain[-1]),
                }
        self.current_transaction = [] # reset the current list of transactions

        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount):
        """
        param: sender <str>
               recipient <str>
               amount <int>
        return: <int> index of block this will hold this transaction
        """

        self.current_transaction.append ({
                "sender" : sender,
                "recipient" : recipient,
                "amount" : amount,
        })

        return self.last_block['index'] + 1

    @staticmethod
    def hash(block):
        """ param: <dict> Block
            return: <str>
        Creats a SHA-256 hash of a Block
        """
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

    def proof_of_work(self, last_proof):
        """
        Simple alg: find a number p' that hash(pp') contains leading 4 zeros, where p is previous proof, p' is new
        """
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    @staticmethod
    def valid_proof (last_proof, proof):
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4]=="0000"

    def valid_chain (self, chain):
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print (f'{last_block}')
            print (f'{block}')
            print ("\n----------------\n")
            # Check the hash correct
            if block['previous_hash'] != self.hash(last_block):
                return False

            # Check POW
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts (self):
        """
        Consensus alg to resolve conflicts by replacing our chain with the longest one in the network
        return True if our chain was replaced, False if not
        """

        neighbours = self.nodes
        new_chain = None

        max_length = len (self.chain)

        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain  = response.json()['chain']

                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True

        return False

# Instantiate Node
app = Flask (__name__)

# Generate a globally unique addr for this node
node_identifier = str(uuid4()).replace('-','')
#Instantiate the Block chain
blockchain = Blockchain()

@app.route ('/mine', methods=['GET'])
def mine ():
    # Run the POW to get next proof ...
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work (last_proof)

    # Receive a reward for finding the proof
    # Sender is "0" to signify that this node has mined a new coin
    blockchain.new_transaction ( sender="0", recipient=node_identifier, amount=1)
    block = blockchain.new_block(proof)

    response = {
            'message': "New Block Forged",
            'index': block['index'],
            'transaction': block['transaction'],
            'proof':block['proof'],
            'previous_hash': block['previous_hash'],
            }
    return jsonify(response), 200

@app.route ('/transactions/new', methods=['POST'])
def new_transaction ():
    values = request.get_json()

    required = ['sender', 'recipient', 'amount']
    if not all (k in values for k in required):
        return 'Missing values', 400

    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])
    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201

@app.route ('/chain', methods=['GET'])
def full_chain ():
    response = {
            'chain': blockchain.chain,
            'length': len(blockchain.chain),
            }
    return jsonify(response), 200

@app.route ('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node (node)

    response = {
            'message': "New nodes have been added",
            'total_nodes': list(blockchain.nodes),
            }
    return jsonify(response), 201

@app.route ('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()
    if replaced:
        response = {
                'message': "Our chain was replaced",
                'new_chain': blockchain.chain
                }
    else:
        response = {
                'message': 'Our chain is authoritative',
                'chain': blockchain.chain
                }

    return jsonify(response), 200

if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port
    print (f'The node is going to run at port {port}')

    app.run(host='127.0.0.1', port=port)

