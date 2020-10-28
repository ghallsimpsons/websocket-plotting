#!/usr/bin/env python3
import eventlet
eventlet.monkey_patch()

import time
import numpy as np
from collections import defaultdict

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from threading import Lock

app = Flask(__name__)
app.config['SECRET_KEY'] = 'NOT_SECRET'
socketio = SocketIO(app)

@app.route('/')
def index():
    return render_template('index.html')

client_lock = Lock()
# {sid: set({registers})}
clients = {}

# {register: last_value}
vals = {'foo': [0]*20,
        'bar': [0]*20,
        'time': [0]*20,
        'sine': [0]*20,
        'dirty_sine': [0]*20}

def get_regs(sid):
    """
    Return dict containing all registers `sid` is subscribed to
    """
    # TODO: If only subscribed to slow, send [vals[reg][0]]
    return {reg: vals[reg] for reg in clients[sid]}

class DummyDataSource:
    """
    A dummy source of data.
    """
    def update(self, tick):
        """
        Update the values of the existing registers.
        """
        vals['foo'][tick] = np.round(np.random.rand(), 3)
        vals['bar'][tick] = np.round(np.random.rand(), 3)
        vals['time'][tick] = time.time()
        vals['sine'][tick] = np.sin(time.time())
        vals['dirty_sine'][tick] = 1.3*np.sin(time.time()+1)+np.random.normal(scale=.1)

def data_task(data_source):
    """
    Grab data from some data producer and send to clients.
    """
    def send_updates():
        client_lock.acquire()
        for sid in clients:
            socketio.emit('data', {'values': get_regs(sid)}, room=sid)
        client_lock.release()

    tick = 0
    while True:
        time.sleep(.05)
        data_source.update(tick)
        # Should maybe run in different thread, but requires synchronization
        if tick == 19:
            send_updates()
            tick = 0
        else:
            tick += 1

@socketio.on('connect')
def subscribe():
    """
    Add new connection to subscribers list.
    """
    print("Got new subscriber")
    client_lock.acquire()
    clients[request.sid] = defaultdict(lambda: {'fast': 0, 'slow': 0})
    client_lock.release()
    emit('connect', {'success': True}, room=request.sid)

@socketio.on('disconnect')
def unsubscribe():
    """
    Remove broken connection from subscribers list.
    """
    client_lock.acquire()
    print("Unsubscribing")
    del clients[request.sid]
    client_lock.release()

@socketio.on('add-register')
def add_register(msg):
    """
    Add a register to the set of registers this client will receive.
    """
    print(f"Adding register {msg['register']}")
    reg = msg['register']
    # TODO: Allow differentiation between fast and slow subscriptions
    if reg not in vals:
        emit('add-register-result', {
            "success": False,
            "register": reg,
            "error": f"Register '{reg}' not found"
            }, room=request.sid)
        return
    client_lock.acquire()
    clients[request.sid][reg]['fast'] += 1
    client_lock.release()
    emit('add-register-result', {
        "success": True,
        "register": reg
        }, room=request.sid)

if __name__ == '__main__':
    data_thread = socketio.start_background_task(data_task,
                                                 data_source=DummyDataSource())
    socketio.run(app)
