#  **********************************************************************************************
#     Class to establish serial communication - in UART and USB - and write and read continuously
#    as block of data
#  **********************************************************************************************

import time
import serial
from threading import Thread


class SerialCommunication:

    def __init__(self, port, baudrate=115200, parity=serial.PARITY_NONE, bytesize=serial.EIGHTBITS,
                 stopbits=serial.STOPBITS_ONE, timeout=1.):

        self.port = port  # param.SERIAL_PORT_NAME if param.isRPI else "/dev/ESP32_actuation_controller"     # "/dev/pool_serial_comm_USB"  #  "/dev/ttyUSB1"
        self.baudrate = baudrate
        self.parity = parity
        self.bytesize = bytesize
        self.stopbits = stopbits
        self.timeout = timeout
        self.newline = "\r\n"

        self.observers = []
        self.halt = False

        self.success = 0
        self.failure = 0

        self.onDataIncoming = null

        self.connThread = None
        self.readBlockThread = None
        self.readForeverThread = None

        self.ser = serial.Serial(
            baudrate=self.baudrate,
            parity=self.parity,
            bytesize=self.bytesize,
            stopbits=self.stopbits,
            timeout=self.timeout)
        # Declare port separately to avoid implicit opening of connection
        self.ser.port = self.port
        # self.connect()

    def connect(self):
        if not self.ser.is_open:
            if self.connThread is not None:
                self.halt = True  # exit previous thread if any
                time.sleep(2.1)
                self.halt = False
            self.connThread = Thread(target=self._connect).start()

    def _connect(self):
        if self.ser.is_open:
            self.ser.close()
        while not self.halt:
            try:
                self.ser.open()
                print(f"\033[92m[UART]:\033[0mUART object created on Port: {self.port} with {str(self.baudrate)} baud")
                break
            except serial.serialutil.SerialException as e:
                e = str(e)
                if "[Errno 13]" in e:
                    print("\033[91m[UART]:\033[0mPERMISSION DENIED")
                elif "[Errno 2]" in e:
                    print(f"\033[91m[UART]:\033[0mNo such port ({self.port})")
                    print("     • Check if your Serial USB is connected")
                # self.ser = None
                print(e)
                # return False
                time.sleep(2)
                continue
        self.connThread = None

    def close_serial(self):
        self.halt = True
        self.ser.close()

    
    # function to read any data received by UART with no analysis, CRC check, just for
    # gui display
    def read_raw(self):
        if self.ser is None:
            print("Uart object none")
            return
        if self.readBlockThread is None:
            self.readBlockThread = Thread(target=self._read_raw)
            self.readBlockThread.start()

    def _read_raw(self):
        self.ser.timeout = None
        rx_data_raw = ""

        while not self.halt:
            if not self.ser.is_open:
                time.sleep(2)
                continue
            try:
                rx_data_raw = self.ser.read(10)
            except serial.serialutil.SerialException as SE:
                print("Serial Exception", SE)
                continue
            if len(rx_data_raw) == 0:
                continue
            # rx_data = rx_data_raw.decode("Latin-1")
            res = self.onDataIncoming(rx_data_raw, False, self.port)

            # print("[ReadRaw]:", "Callback result", res)
            if res is not None and not res:
                self.ser.read(1)
                
            time.sleep(0.005)

    def write(self, data, terminate=True):
        if self.ser is not None:
            if terminate:
                data = str(data) + self.newline
            print("\033[93m[UART] >>\033[0m", data, f"({len(data)} Bytes)")
            self.ser.write(data.encode(param.SERIAL_ENCODING))
            return True
        else:
            return False

    def bind_to(self, callback, uid):
        self.observers.append([callback, uid])
        print("\033[93m[UART]:\033[0m", "Callback added for device id:", uid)


def null(*args, **kwargs) -> int:
    pass


if __name__ == "__main__":
    def dataIncoming(rx_data_raw, *args):
        print(rx_data_raw)
        start_tag = rx_data_raw[:2]
        end_tag = rx_data_raw[-2:]
        if (start_tag != b"$$" or end_tag != b"##"):
            print("UART data framing error")
            return False
        
        payload = rx_data_raw[2:-2]
        channel1 = int.from_bytes(payload[0:2], byteorder='big')
        channel2 = int.from_bytes(payload[2:4], byteorder='big')
        channel3 = int.from_bytes(payload[4:6], byteorder='big')
        print("\t", {'ch1': channel1, 'ch2': channel2, 'ch3': channel3})


    uart1 = SerialCommunication('/dev/ttyUSB0', baudrate=115200, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0.5)
    uart1.connect()
    uart1.onDataIncoming = dataIncoming
    time.sleep(1)
    uart1.read_raw()
    # while True:
        # pass
        # uart.write("hello")
        # time.sleep(1)

