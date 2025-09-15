import machine
import bluetooth
import struct
import time
from micropython import const
from machine import Pin
from ble_advertising import advertising_payload

_IRQ_CENTRAL_CONNECT    = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE        = const(3)

MIDI_SERVICE_UUID = bluetooth.UUID('03B80E5A-EDE8-4B33-A751-6CE34EC4C700')
MIDI_CHAR_UUID    = bluetooth.UUID('7772E5DB-3868-4112-A1A9-F2669D106BF3')
BLE_MIDI_CHAR     = (MIDI_CHAR_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY | bluetooth.FLAG_WRITE | bluetooth.FLAG_WRITE_NO_RESPONSE)
BLE_MIDI_SERVICE  = (MIDI_SERVICE_UUID, (BLE_MIDI_CHAR,))
SERVICES = (BLE_MIDI_SERVICE, )
PAYLOAD  = advertising_payload(name="PicoMIDI", services=[MIDI_SERVICE_UUID])

isConnected = False
timestamp = 0
bt = bluetooth.BLE()
conn_handle = None
midi_handle = None

def sendNote(channel, note, velocity):
    global bt, conn_handle, midi_handle, timestamp
    if not isConnected: return
    timestamp = (timestamp + 1) & 0x1FFF # 타임스탬프 롤오버 방지
    status = 0x90 | (channel & 0x0f) if velocity > 0 else 0x80 | (channel & 0x0f)
    txdata = bytearray([0x80 | (timestamp >> 7), 0x80 | (timestamp & 0x7f), status, note, velocity])
    bt.gatts_notify(conn_handle, midi_handle, txdata)
    print("send", txdata)

def sendCC(channel, number, value):
    global bt
    global conn_handle
    global midi_handle
    global timestamp

    timestamp += 1
    status = 0xb0 | (channel & 0x0f)  # CC
    txdata = bytearray([0x80 | (timestamp >> 7), 0x80 | (timestamp & 0x7f), status, number, value])
    bt.gatts_notify(conn_handle, midi_handle, txdata)
    print("send", txdata)

def parseMidiData(data):
    print("parse", data)
    if ((data[0] & 0x80) == 0) | ((data[1] & 0x80) == 0):
        return

    length = len(data)
    n = 2
    while (n + 2 < length):
        if ((data[n] & 0xf0) == 0x80):
            # Note Off
            a = data[n + 1] & 0x7f
            b = data[n + 2] & 0x7f
            print("NoteOff", a, b)
            n += 2

        elif ((data[n] & 0xf0) == 0x90):
            # Note On
            a = data[n + 1] & 0x7f
            b = data[n + 2] & 0x7f
            print("NoteOn", a, b)
            n += 2

        elif ((data[n] & 0xf0) == 0xb0):
            # Control Change
            a = data[n + 1] & 0x7f
            b = data[n + 2] & 0x7f
            print("CC", a, b)
            n += 2

        n += 1

def isrBt(event, data):
    global conn_handle, isConnected
    if event == _IRQ_CENTRAL_CONNECT:
        conn_handle, _, _ = data
        isConnected = True
        print("Connected", conn_handle)
    elif event == _IRQ_CENTRAL_DISCONNECT:
        conn_handle, _, _ = data
        isConnected = False
        print("Disconnected", conn_handle)
        bt.gap_advertise(500000, adv_data=PAYLOAD)
    elif event == _IRQ_GATTS_WRITE:
        conn_handle, value_handle = data
        rxdata = bt.gatts_read(value_handle)
        parseMidiData(rxdata)


def work():
    global bt, conn_handle, midi_handle, isConnected

    led = Pin('LED', Pin.OUT)

    row_pins = [Pin(0, Pin.OUT), Pin(1, Pin.OUT)]
    col_pins = [Pin(i, Pin.IN, Pin.PULL_UP) for i in range(10, 22)]
    
    num_rows = len(row_pins)
    num_cols = len(col_pins)
    
    key_states = [[True] * num_cols for _ in range(num_rows)]

    bt.irq(isrBt)
    bt.active(True)
    ((midi_handle,),) = bt.gatts_register_services(SERVICES)
    bt.gap_advertise(500000, adv_data=PAYLOAD)
    print("Advertising", midi_handle)

    while True:
        for row_idx, row_pin in enumerate(row_pins):
            row_pin.value(0)
            for col_idx, col_pin in enumerate(col_pins):
                current_state = col_pin.value() == 1
                if current_state != key_states[row_idx][col_idx]:
                    key_states[row_idx][col_idx] = current_state
                    midi_note = (60 + row_idx * 12) + col_idx
                    
                    if not current_state:
                        print(f"Note On: Octave {row_idx+1}, Note {col_idx} -> MIDI {midi_note}")
                        sendNote(0, midi_note, 100)
                    else:
                        print(f"Note Off: Octave {row_idx+1}, Note {col_idx} -> MIDI {midi_note}")
                        sendNote(0, midi_note, 0)
            row_pin.value(1)

        led.toggle()
        time.sleep_ms(10)
 

if __name__ == "__main__":
    work()

