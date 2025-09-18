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

octab = 0

def sendNote(channel, note, velocity):
    global bt, conn_handle, midi_handle, timestamp
    if not isConnected: return
    timestamp = (timestamp + 1) & 0x1FFF
    status = 0x90 | (channel & 0x0f) if velocity > 0 else 0x80 | (channel & 0x0f)
    txdata = bytearray([0x80 | (timestamp >> 7), 0x80 | (timestamp & 0x7f), status, note, velocity])
    bt.gatts_notify(conn_handle, midi_handle, txdata)

def sendCC(channel, number, value):
    global bt, conn_handle, midi_handle, timestamp
    if not isConnected: return
    timestamp = (timestamp + 1) & 0x1FFF
    status = 0xb0 | (channel & 0x0f)
    txdata = bytearray([0x80 | (timestamp >> 7), 0x80 | (timestamp & 0x7f), status, number, value])
    bt.gatts_notify(conn_handle, midi_handle, txdata)
    print("Sent CC:", txdata)

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

def function_button_0_action():
    print("Function Button 0 (GPIO 10) Pressed!")

def function_button_1_action():
    print("Function Button 1 (GPIO 11) Pressed!")

def function_button_2_action():
    print("Function Button 2 (GPIO 12) Pressed!")

def function_button_3_action():
    print("Function Button 3 (GPIO 13) Pressed!")

def function_button_4_action():
    print("Function Button 4 (GPIO 14) Pressed!")

def function_button_5_action():
    print("Function Button 5 (GPIO 15) Pressed!")

def function_button_6_action():
    global octab
    octab = -5 if octab==-5 else octab-1
    print("Function Button 6 (GPIO 16) Pressed!")

def function_button_7_action():
    global octab
    octab = 10 if octab==10 else octab+1
    print("Function Button 7 (GPIO 17) Pressed!")

function_actions = [
    function_button_0_action, function_button_1_action, function_button_2_action, function_button_3_action,
    function_button_4_action, function_button_5_action, function_button_6_action, function_button_7_action
]

def work():
    global bt, conn_handle, midi_handle, isConnected

    led = Pin('LED', Pin.OUT)

    key_rows = [Pin(0, Pin.OUT), Pin(1, Pin.OUT)]
    key_cols = [Pin(i, Pin.IN, Pin.PULL_UP) for i in range(10, 22)]
    
    func_row = Pin(9, Pin.OUT)
    func_cols = [Pin(i, Pin.IN, Pin.PULL_UP) for i in range(10, 18)]

    key_states = [[True] * len(key_cols) for _ in range(len(key_rows))]
    func_key_states = [True] * len(func_cols)

    bt.irq(isrBt)
    bt.active(True)
    ((midi_handle,),) = bt.gatts_register_services(SERVICES)
    bt.gap_advertise(500000, adv_data=PAYLOAD)
    print("Advertising", midi_handle)

    while True:
        for row_idx, row_pin in enumerate(key_rows):
            row_pin.value(0)
            for col_idx, col_pin in enumerate(key_cols):
                current_state = col_pin.value() == 1
                if current_state != key_states[row_idx][col_idx]:
                    key_states[row_idx][col_idx] = current_state
                    midi_note = (60 + (row_idx+octab) * 12) + col_idx
                    if not current_state:
                        sendNote(0, midi_note, 100)
                    else:
                        sendNote(0, midi_note, 0)
            row_pin.value(1)

        func_row.value(0)
        for col_idx, col_pin in enumerate(func_cols):
            current_state = col_pin.value() == 1
            if not func_key_states[col_idx] and current_state:
                function_actions[col_idx]()
            func_key_states[col_idx] = current_state
        func_row.value(1)

        led.toggle()
        time.sleep_ms(5)
 

if __name__ == "__main__":
    work()


