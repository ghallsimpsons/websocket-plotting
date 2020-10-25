#!/usr/bin/env python3
import eventlet
eventlet.monkey_patch()

import time
import numpy as np

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'NOT_SECRET'
socketio = SocketIO(app)

@app.route('/')
def index():
    return render_template('index.html')

# {sid: set({registers})}
clients = {}

# {register: last_value}
vals = {'foo': 0, 'bar': 0}

def get_regs(sid):
    """
    Return dict containing all registers `sid` is subscribed to
    """
    return {reg: vals[reg] for reg in clients[sid]}

class DummyDataSource:
    """
    A dummy source of data.
    """
    def update(self):
        """
        Update the values of the existing registers.
        """
        vals['foo'] = np.round(np.random.rand(), 3)
        vals['bar'] = np.round(np.random.rand(), 3)

def data_task(data_source):
    """
    Grab data from some data producer and send to clients.
    """
    def send_updates():
        for sid in clients:
            socketio.emit('data', {'values': get_regs(sid)}, room=sid)

    while True:
        time.sleep(5)
        data_source.update()
        # Should maybe run in different thread, but requires synchronization
        send_updates()

@socketio.on('connect')
def subscribe():
    """
    Add new connection to subscribers list.
    """
    print("Got new subscriber")
    clients[request.sid] = set()
    emit('connect', {'success': True}, room=request.sid)

@socketio.on('disconnect')
def unsubscribe():
    """
    Remove broken connection from subscribers list.
    """
    del clients[request.sid]

@socketio.on('add-register')
def add_register(msg):
    """
    Add a register to the set of registers this client will receive.
    """
    print(f"Adding register {msg['register']}")
    reg = msg['register']
    if reg not in vals:
        emit('add-register-result', {
            "success": False,
            "register": reg,
            "error": f"Register '{reg}' not found"
            }, room=request.sid)
        return
    clients[request.sid].add(reg)
    emit('add-register-result', {
        "success": True,
        "register": reg
        }, room=request.sid)

if __name__ == '__main__':
    data_thread = socketio.start_background_task(data_task,
                                                 data_source=DummyDataSource())
    socketio.run(app)
