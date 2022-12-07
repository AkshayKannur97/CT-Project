from itertools import product
from kivy.config import Config
Config.set('graphics', 'width', '1024')
Config.set('graphics', 'height', '600')
Config.set('kivy','keyboard_mode','systemanddock')     # 'systemandmulti', 'systemanddock', 'multi'

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.clock import Clock, mainthread
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import ScreenManager, Screen

"""
Graph References:
    https://github.com/kivy-garden/graph
    https://stackoverflow.com/questions/30821127/using-kivy-garden-graph-in-kv-language#answer-46522799

"""
from math import sin
import random
from kivy_garden.graph import Graph, MeshLinePlot

import os
import time
import sqlite3
from threading import Timer
from datetime import datetime


try:
    import RPi.GPIO as gpio
    Config.set('graphics', 'fullscreen', '1')
    UART_PORT = "/dev/serial0"
except:
    print("Running on a non-raspberry device. Hence loading proxy GPIO library")
    import GPIO as gpio
    UART_PORT = "/dev/ttyUSB0"

import uart_read
import db_utils


""" Function to regularly update Date and Time in environment variable """
def clock(*args):
    now = datetime.now()
    date = datetime.strftime(now, '%d/%m/%Y')
    time = datetime.strftime(now, '%H:%M:%S')
    os.environ['DATE'] = date
    os.environ['TIME'] = time

Clock.schedule_interval(clock, 1)


""" Create uart object and read continuously and pass data to subscriber screens """
UART_CHANNEL_SUBSCRIBERS = []

def uart_channel_subscribe(callback):
    UART_CHANNEL_SUBSCRIBERS.append(callback)

class Calculation:
    def __init__(self, channel, tare=0) -> None:
        # channel should be same as provided in 'Calibration' database
        self.channel = channel
        self.decimal_point = None; self.resolution = None; self.max_capacity = None
        self.cal_capacity = None; self.cal_zero = None; self.cal_span = None
        self.output = 0
        self.tare = tare
        self.set_parameters()

    def set_parameters(self):
        # fetch calibration data from database
        calibration_data = db_utils.fetch_calibration_for_channel(self.channel) 
        # extract calibration data
        self.decimal_point = calibration_data[1]
        self.resolution = calibration_data[2]
        self.max_capacity = calibration_data[3]
        self.cal_capacity = calibration_data[4]
        self.cal_zero = calibration_data[5]
        self.cal_span = calibration_data[6]
        # calculate multiplication factor from calibration data
        #    MF = cal_capacity / (cal_span - cal_zero)      -> for load cell
        #    MF = length-per-rotation / step-per-rotation   -> for encoder
        self.mf = self.cal_capacity / (self.cal_span - self.cal_zero or 1)
        print("[MULTIPLICATION FACTOR]:", self.channel, self.mf)

    def calc(self, raw_adc_value) -> float:
        self.output = (raw_adc_value - self.cal_zero) * self.mf - self.tare
        return self.output

    def do_tare(self, value) -> None:
        self.tare = self.output + self.tare

    def calibrate(self, value) -> None:
        self.cal_zero = value

ch1_calculator = Calculation(channel='ch1')
ch2_calculator = Calculation(channel='ch2')
ch3_calculator = Calculation(channel='ch3')

def uart_data_incoming(rx_data_raw, *args):
    start_tag = rx_data_raw[:2]
    end_tag = rx_data_raw[-2:]
    if (start_tag != b"$$" or end_tag != b"##"):
        print("UART data framing error")
        return False
    
    payload = rx_data_raw[2:-2]
    channel1_adc = int.from_bytes(payload[0:2], byteorder='big', signed=True)
    channel2_adc = int.from_bytes(payload[2:4], byteorder='big', signed=True)
    channel3_adc = int.from_bytes(payload[4:6], byteorder='big', signed=True)
    info = {
        'ch1': ch1_calculator.calc(channel1_adc),
        'ch2': ch2_calculator.calc(channel2_adc),
        'ch3': ch3_calculator.calc(channel3_adc),
        'ch1_adc': channel1_adc,
        'ch2_adc': channel2_adc,
        'ch3_adc': channel3_adc
    }
    
    for callback in UART_CHANNEL_SUBSCRIBERS:
        callback(info)

uart = uart_read.SerialCommunication(UART_PORT, baudrate=115200)
uart.connect()
uart.onDataIncoming = uart_data_incoming
time.sleep(0.1)
# start reading the UART after loading the kv builder file:
    # uart.read_raw()


"""
    Class to manage Splash Screen
"""
class WindowSplash(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        Timer(5, self.end_splash).start()

    def end_splash(self):
        self.manager.current = 'layout_login'
        

"""
    Class to manage Home Screen
"""
class WindowLogin(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        
        # wait until kv file is loaded to fetch element by id
        # Clock.schedule_interval(self.clock, 1)

    def clock(self, *args):
        self.ids.calendar.text = os.environ.get('DATE')
        self.ids.clock.text = os.environ.get('TIME')

    def login(self):
        self.ids.message.text = ""
        # fetch user credentials from screen
        username = self.ids.username.text
        password = self.ids.password.text
        if username == "":
            self.manager.current = 'layout_home'
            return
        # fetch user credentials from db
        psw = None
        conn = sqlite3.connect('./data.db')
        sql = f'''SELECT password FROM Users WHERE name="{username}";'''
        print(sql)
        cur = conn.cursor()
        try:
            cur.execute(sql)
        except sqlite3.OperationalError as e:
            print(e)
        else:
            psw = cur.fetchone()
            print(psw)
            if psw is None or psw[0] != password:
                print("Wrong credentials")
                self.ids.message.text = "Wrong credentials"
                return
            else:
                self.manager.current = 'layout_home'


"""
    Class to manage Home Screen
"""
class WindowHome(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        
        # wait until kv file is loaded to fetch element by id
        Clock.schedule_interval(self.clock, 1)
        self.enable_operate_buttons(1)
        uart_channel_subscribe(self.update_reading_fom_uart)

    def clock(self, *args):
        self.ids.calendar.text = os.environ.get('DATE')
        self.ids.clock.text = os.environ.get('TIME')

    def load_tare(self):
        current_value = float(self.ids.label_load.text)
        self.ids.label_load.text = "0.00"
        ch1_calculator.do_tare(current_value)

    def displacement_tare(self):
        current_value = float(self.ids.label_displacement.text)
        self.ids.label_displacement.text = "0.000"
        ch3_calculator.do_tare(current_value)

    @mainthread
    def enable_operate_buttons(self, disabled):
        self.ids.button_operate_up.disabled = disabled
        self.ids.button_operate_fast.disabled = disabled
        self.ids.button_operate_slow.disabled = disabled
        self.ids.button_operate_down.disabled = disabled

    def update_reading_fom_uart(self, info, *args):
        print("\t", info)
        self.ids.label_load.text = format(info.get('ch1', 0), '.2f')
        self.ids.label_displacement.text = format(info.get('ch3', 0), '.3f')


"""
    Class to manage Test Config 1 Screen
"""
class WindowTC1(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.test_id = 0
        # wait until kv file is loaded to fetch element by id
        Clock.schedule_interval(self.clock, 1)
        # Timer(1, self.fetch_next_id).start()
        # Clock.schedule_once(self.fetch_next_id, 0)

    def clock(self, *args):
        self.ids.calendar.text = os.environ.get('DATE')
        self.ids.clock.text = os.environ.get('TIME')

    def enable_next_button(self):
        disable = 0
        if not self.ids.input_mid.text:
            disable = 1
        if not self.ids.input_lot.text:
            disable = 1
        if not self.ids.input_iid.text:
            disable = 1
        print("Enabling...", disable)
        # self.ids.next.disabled = disable

    def fetch_next_id(self):
        conn = sqlite3.connect('./data.db')
        sql = f''' SELECT * FROM Tests ORDER BY id DESC LIMIT 1 '''
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchone()
        self.test_id = (rows[0] or 0) + 1
        print("Test Id:", self.test_id)
        self.ids.label_id.text = str(self.test_id)

    def save_to_db(self):
        _id = 1
        _mid = self.ids.input_mid.text
        _lot = self.ids.input_lot.text
        _iid = self.ids.input_iid.text
        _rem = self.ids.input_remarks.text

        conn = sqlite3.connect('./data.db')
        sql = f''' INSERT INTO Tests(id, mid, lot, iid, remarks)
              VALUES(?, ?, ?, ?, ?) '''
        print(sql)
        cur = conn.cursor()
        cur.execute(sql, (_id, _mid, _lot, _iid, _rem))
        conn.commit()

    def customer_vendor_selection(self):
        category = self.ids.spinner_main.text
        if (category == "Customer"):
            self.populate_customer_spinner()
        elif (category == "Vendor"):
            self.populate_vendor_spinner()

    """When customer/vendor code is selected, name to be displayed"""
    def code_selection(self):
        category = self.ids.spinner_main.text
        record = ()
        if (category == "Customer"):
            record = self.fetch_customer_record()
        elif (category == "Vendor"):
            record = self.fetch_vendor_record()
        print(record)
        self.ids.label_name.text = record[1]

    def fetch_customer_list(self):
        conn = sqlite3.connect('./data.db')
        sql = f''' SELECT * FROM Customers '''
        print(sql)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        return rows

    def fetch_vendor_list(self):
        conn = sqlite3.connect('./data.db')
        sql = f''' SELECT * FROM Vendors '''
        print(sql)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        return rows
        
    def fetch_customer_record(self):
        conn = sqlite3.connect('./data.db')
        sql = f''' SELECT * FROM Customers WHERE code=? '''
        code = self.ids.spinner_master.text
        print(sql, code)
        cur = conn.cursor()
        cur.execute(sql, (code,))
        row = cur.fetchone()
        return row

    def fetch_vendor_record(self):
        conn = sqlite3.connect('./data.db')
        sql = f''' SELECT * FROM Vendors WHERE code=? '''
        code = self.ids.spinner_master.text
        print(sql)
        cur = conn.cursor()
        cur.execute(sql, (code,))
        row = cur.fetchone()
        return row

    def populate_customer_spinner(self):
        values = []
        rows = self.fetch_customer_list()
        for row in rows:
            values.append(row[0])
        self.ids.spinner_master.values = values

    def populate_vendor_spinner(self):
        values = []
        rows = self.fetch_vendor_list()
        for row in rows:
            values.append(row[0])
        self.ids.spinner_master.values = values

    def product_code_selection(self):
        record = self.fetch_material_record() or []
        print(record)
        self.ids.label_product_name.text = record[1]
        self.ids.label_product_description.text = record[2]
        self.ids.label_product_min.text = str(record[3])
        self.ids.label_product_max.text = str(record[4])
        self.ids.label_product_size.text = str(record[5])

    def populate_material_spinner(self):
        conn = sqlite3.connect('./data.db')
        sql = f''' SELECT * FROM Materials '''
        print(sql)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        values = []
        for row in rows:
            values.append(row[0])
        self.ids.spinner_product_master.values = values
        
    def fetch_material_record(self):
        conn = sqlite3.connect('./data.db')
        sql = f''' SELECT * FROM materials WHERE code=? '''
        code = self.ids.spinner_product_master.text
        print(sql, code)
        cur = conn.cursor()
        cur.execute(sql, (code,))
        row = cur.fetchone()
        return row


"""
    Class to manage Test Config 2 Screen
"""
class WindowTC2(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        # wait until kv file is loaded to fetch element by id
        Clock.schedule_interval(self.clock, 1)

    def clock(self, *args):
        self.ids.calendar.text = os.environ.get('DATE')
        self.ids.clock.text = os.environ.get('TIME')

    def customer_vendor_selection(self):
        category = self.ids.spinner_main.text
        if (category == "Customer"):
            self.populate_customer_spinner()
        elif (category == "Vendor"):
            self.populate_vendor_spinner()

    """When customer/vendor code is selected, name to be displayed"""
    def code_selection(self):
        category = self.ids.spinner_main.text
        record = ()
        if (category == "Customer"):
            record = self.fetch_customer_record()
        elif (category == "Vendor"):
            record = self.fetch_vendor_record()
        print(record)
        self.ids.label_name.text = record[1]

    def fetch_customer_list(self):
        conn = sqlite3.connect('./data.db')
        sql = f''' SELECT * FROM Customers '''
        print(sql)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        return rows

    def fetch_vendor_list(self):
        conn = sqlite3.connect('./data.db')
        sql = f''' SELECT * FROM Vendors '''
        print(sql)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        return rows
        
    def fetch_customer_record(self):
        conn = sqlite3.connect('./data.db')
        sql = f''' SELECT * FROM Customers WHERE code=? '''
        code = self.ids.spinner_master.text
        print(sql, code)
        cur = conn.cursor()
        cur.execute(sql, (code,))
        row = cur.fetchone()
        return row

    def fetch_vendor_record(self):
        conn = sqlite3.connect('./data.db')
        sql = f''' SELECT * FROM Vendors WHERE code=? '''
        code = self.ids.spinner_master.text
        print(sql)
        cur = conn.cursor()
        cur.execute(sql, (code,))
        row = cur.fetchone()
        return row

    def populate_customer_spinner(self):
        values = []
        rows = self.fetch_customer_list()
        for row in rows:
            values.append(row[0])
        self.ids.spinner_master.values = values

    def populate_vendor_spinner(self):
        values = []
        rows = self.fetch_vendor_list()
        for row in rows:
            values.append(row[0])
        self.ids.spinner_master.values = values


"""
    Class to manage Test Config 3 Screen
"""
class WindowTC3(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        # wait until kv file is loaded to fetch element by id
        Clock.schedule_interval(self.clock, 1)
        # Clock.schedule_once(self.populate_material_spinner, 0)

    def clock(self, *args):
        self.ids.calendar.text = os.environ.get('DATE')
        self.ids.clock.text = os.environ.get('TIME')

    def code_selection(self):
        record = self.fetch_material_record()
        print(record)
        self.ids.label_name.text = record[1]
        self.ids.label_description.text = record[2]
        self.ids.label_min.text = str(record[3])
        self.ids.label_max.text = str(record[4])
        self.ids.label_size.text = str(record[5])

    def populate_material_spinner(self):
        conn = sqlite3.connect('./data.db')
        sql = f''' SELECT * FROM Materials '''
        print(sql)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        values = []
        for row in rows:
            values.append(row[0])
        self.ids.spinner_master.values = values
        
    def fetch_material_record(self):
        conn = sqlite3.connect('./data.db')
        sql = f''' SELECT * FROM materials WHERE code=? '''
        code = self.ids.spinner_master.text
        print(sql, code)
        cur = conn.cursor()
        cur.execute(sql, (code,))
        row = cur.fetchone()
        return row

    def confirm(self):
        mid = self.manager.get_screen("layout_tc1").ids.input_mid.text
        lot = self.manager.get_screen("layout_tc1").ids.input_lot.text
        iid = self.manager.get_screen("layout_tc1").ids.input_iid.text
        cust_vend_code = self.manager.get_screen("layout_tc2").ids.spinner_master.text
        cust_vend_name = self.manager.get_screen("layout_tc2").ids.label_name.text
        product_code = self.manager.get_screen("layout_tc3").ids.spinner_master.text
        print("\n======================================================")
        print(f"Machine ID: {mid}\nLot: {lot}\nInvoice ID: {iid}\nCustomer/Vendor Code: {cust_vend_code}\nCustomer/Vendor Name: {cust_vend_name}\nProduct Code: {product_code}")
        print("======================================================")


"""
    Class to manage Testing Screen
"""
class WindowTesting(Screen, Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        
        self.is_graph_live = False
        self.graph = None
        self.plot = None
        
        self.generate_graph()
        
        # wait until kv file is loaded to fetch element by id
        Clock.schedule_interval(self.clock, 1)
        uart_channel_subscribe(self.update_graph_fom_uart)

    def clock(self, *args):
        self.ids.calendar.text = os.environ.get('DATE')
        self.ids.clock.text = os.environ.get('TIME')

    @mainthread
    def generate_graph(self):
        self.graph = self.ids['graph_test']
        self.plot = MeshLinePlot(color=[1, 0, 0, 1])
        # self.plot.points = [(x, sin(x / 10.)) for x in range(0, 101)]
        self.graph.add_plot(self.plot)

    @mainthread
    def update_graph_fom_uart(self, info, *args):
        if not self.is_graph_live:
            return
        load = info.get('ch1', 0)
        disp = info.get('ch3', 0)
        self.ids.label_load.text = format(load, '.2f')
        self.ids.label_displacement.text = format(disp, '.3f')
        # ignore if x value (displacement) received is same as previous
        if (self.plot.points or [(0, )])[-1][0] == disp:
            return
        self.plot.points.append((disp, load))
        self.graph.xmax = max(self.graph.xmax, disp + 1)
        self.graph.ymax = max(self.graph.ymax, load + 1)

    def control_graph(self):
        if self.ids.button_graph_control.text == "START":
            self.ids.button_graph_control.text = "STOP"
            self.is_graph_live = True
        else:
            self.ids.button_graph_control.text = "START"
            self.is_graph_live = False

    def reset_graph(self):
        self.plot.points = []
 

"""
    Class to manage Calibration Screen
"""
class WindowCalibration(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        self.channel1 = 'ch1_adc'
        self.channel2 = 'ch2_adc'
        self.channel3 = 'ch3_adc'
        self.process_cal = 10
        self.process_span = 11
        self.cal_duration_sec = 5

        self.start_cal_process = False
        self.cal_process = self.process_cal
        self.cal_channel = self.channel1
        self.cal_readings = []

        self.sync_data_from_db()

        # wait until kv file is loaded to fetch element by id
        # Clock.schedule_interval(self.clock, 1)

        uart_channel_subscribe(self.adc_read_fom_uart)

    def clock(self, *args):
        self.ids.calendar.text = os.environ.get('DATE')
        self.ids.clock.text = os.environ.get('TIME')

    @mainthread
    def sync_data_from_db(self):
        ch1_calibration_data = db_utils.fetch_calibration_for_channel('ch1') 
        self.ids.ch1_decimal_point.text = str(ch1_calibration_data[1])
        self.ids.ch1_resolution.text = str(ch1_calibration_data[2])
        self.ids.ch1_max_capacity.text = str(ch1_calibration_data[3])
        self.ids.ch1_cal_capacity.text = str(ch1_calibration_data[4])
        ch3_calibration_data = db_utils.fetch_calibration_for_channel('ch3') 
        self.ids.ch3_cal_span.text = str(ch3_calibration_data[6])
        self.ids.ch3_cal_capacity.text = str(ch3_calibration_data[4])
        self.ids.ch3_max_capacity.text = str(ch3_calibration_data[3])

    def adc_read_fom_uart(self, info, *args):
        self.ids.ch1_raw_adc.text = str(info.get('ch1_adc', 0))
        self.ids.ch3_raw_adc.text = str(info.get('ch3_adc', 0))
        if not self.start_cal_process:
            if self.cal_readings:
                print("Calibration ended, processing")
                self.post_process()
                self.cal_readings = []
            return
        adc_reading = info.get(self.cal_channel)
        self.cal_readings.append(adc_reading)
        print("\t[CALIBRATION]:", adc_reading)

    """ Function to be performed when user click calibration/span button
            Start calibration process, read ADC for set duratrion and average
     """
    def do_calibration(self, channel, process):
        def end_calibration():
            print("Ending calibration process")
            self.start_cal_process = False
       
        print("Starting calibration process")
        self.cal_channel = channel
        self.cal_process = process
        self.start_cal_process = True
        Timer(self.cal_duration_sec, end_calibration).start()

    """ Process to be done after adc readings collected """
    def post_process(self):
        average_adc_reading = round(sum(self.cal_readings) / (len(self.cal_readings) or 1))
        print("===============================================")
        print("[CALIBRATED]:", average_adc_reading)
        print("===============================================")

        kwargs = {'cal_zero' if self.cal_process == self.process_cal else 'cal_span': average_adc_reading}
        if self.cal_channel == self.channel1:       # Load cell channel
            db_utils.update_calibration_for_channel('ch1', **kwargs)
            ch1_calculator.set_parameters()
        elif self.cal_channel == self.channel2:       # Extensometer channel
            db_utils.update_calibration_for_channel('ch2', **kwargs)
            ch2_calculator.set_parameters()
        elif self.cal_channel == self.channel3:       # Encoder channel
            db_utils.update_calibration_for_channel('ch3', **kwargs)
            ch3_calculator.set_parameters()

    """ Function to read user input and save to database """
    def save_calibration_data(self):
        ch1_decimal_point = self.ids.ch1_decimal_point.text
        ch1_resolution = self.ids.ch1_resolution.text
        ch1_max_capacity = self.ids.ch1_max_capacity.text
        ch1_cal_capacity = self.ids.ch1_cal_capacity.text
        ch3_cal_span = self.ids.ch3_cal_span.text
        ch3_cal_capacity = self.ids.ch3_cal_capacity.text
        ch3_max_capacity = self.ids.ch3_max_capacity.text

        db_utils.update_calibration_for_channel('ch1', decimal=ch1_decimal_point, resolution=ch1_resolution, max_capacity=ch1_max_capacity, cal_capacity=ch1_cal_capacity)
        ch1_calculator.set_parameters()
        db_utils.update_calibration_for_channel('ch3', cal_span=ch3_cal_span, max_capacity=ch3_max_capacity, cal_capacity=ch3_cal_capacity)
        ch3_calculator.set_parameters()


"""
    Class to manage Calibration Screen
"""
class WindowDiagnostics(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        uart_channel_subscribe(self.update_reading_fom_uart)

    def update_reading_fom_uart(self, info, *args):
        self.ids.ch1_raw_adc.text = str(info.get('ch1_adc', 0))
        self.ids.ch3_raw_adc.text = str(info.get('ch3_adc', 0))
        self.ids.ch1_value.text = format(info.get('ch1', 0), '.2f')
        self.ids.ch3_value.text = format(info.get('ch3', 0), '.3f')


"""
    Class to manage all screens
"""
class WindowManager(ScreenManager):
    pass

# Load kv builder file
kv = Builder.load_file('launcher.kv')

# start reading from UART
uart.read_raw()


class CTControlApp(App):
    def build(self):
        Window.clearcolor = (205/255, 205/255, 205/255, 1)
        Window.borderless = 1
        Window.softinput_mode = 'resize'           # '', 'pan', 'resize', 'below_target'
        Window.bind(on_request_close=self.on_request_close)
        return kv

    def on_request_close(self, *args):
        print("Quiting")
        os.environ['terminate'] = '1'
        uart.halt = True

CTControlApp().run()
