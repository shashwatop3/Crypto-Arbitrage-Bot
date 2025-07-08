import socketio
import time

base_url = 'wss://ws.coinswitch.co/'
namespace = '/exchange_2'
pair = 'BTCUSDT'

sio = socketio.Client(logger=True, engineio_logger=True)

@sio.event
def connect():
    print('Connected to Socket.IO server')
    subscribe_data = {
        'event': 'subscribe',
        'pair': pair
    }
    print(f'Subscribing to {pair}...')
    def ack(*args):
        print('Subscription ACK:', args)
    sio.emit('FETCH_TICKER_INFO_CS_PRO', subscribe_data, namespace=namespace, callback=ack)

@sio.event
def connect_error(data):
    print('Connection failed:', data)

@sio.event
def disconnect():
    print('Disconnected from Socket.IO server')

@sio.event
def error(data):
    print('Socket.IO error:', data)

@sio.on('*', namespace=namespace)
def catch_all(event, data):
    print(f'Event: {event}, Data: {data}')

@sio.on('FETCH_TICKER_INFO_CS_PRO', namespace=namespace)
def on_ticker_info(data):
    print('Received ticker info:', data)

if __name__ == "__main__":
    print('Connecting to Socket.IO...')
    try:
        sio.connect(
            url=base_url,
            namespaces=[namespace],
            transports=['websocket'],
            socketio_path='/pro/realtime-rates-socket/futures/exchange_2',
            wait=True,
            wait_timeout=10
        )
    except Exception as e:
        print('Exception during connect:', e)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sio.disconnect()
