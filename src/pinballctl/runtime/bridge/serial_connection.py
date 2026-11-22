"""Open runtime serial without pulsing ESP boot/reset control lines."""
import serial


def open_runtime_serial(port, baud):
    # Passing port to Serial() opens immediately with DTR/RTS asserted. Set both
    # before open, including reconnects, so the application never requests bootloader mode.
    connection = serial.Serial(port=None, baudrate=baud, timeout=0.01, write_timeout=0.25)
    try:
        connection.dtr = False
        connection.rts = False
        connection.port = port
        connection.open()
        return connection
    except Exception:
        connection.close()
        raise
