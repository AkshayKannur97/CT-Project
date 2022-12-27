from kivy.config import Config
Config.set('graphics', 'width', '1024')
Config.set('graphics', 'height', '600')
Config.set('graphics', 'borderless', '1')
Config.set('graphics', 'show_cursor', '1')
Config.set('kivy','default_font', ['DejaVuSans', 'res/fonts/ZenDots-Regular.ttf'])
Config.set('kivy','keyboard_layout', 'qwerty')
Config.set('kivy','keyboard_mode','systemanddock')     # 'systemandmulti', 'systemanddock', 'multi'

try:
    import RPi.GPIO as GPIO
    Config.set('graphics', 'fullscreen', '1')
    UART_PORT = "/dev/serial0"
except:
    print("Running on a non-raspberry device. Hence loading proxy GPIO library")
    import GPIO as GPIO
    UART_PORT = "/dev/ttyUSB0"

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.clock import Clock, mainthread
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.button import Button

from kivy.factory import FactoryException

from kivy.metrics import dp
from kivymd.uix.button import MDFlatButton
from kivymd.app import MDApp
from kivymd.uix.datatables import MDDataTable

"""
Graph References:
    https://github.com/kivy-garden/graph
    https://stackoverflow.com/questions/30821127/using-kivy-garden-graph-in-kv-language#answer-46522799

"""
from math import sin
import random
from kivy_garden.graph import Graph, LinePlot, MeshLinePlot

import os
import sys
import ast
import copy
import time
import json
import sqlite3
from random import random
from threading import Timer
from datetime import datetime

import uart_read
import db_utils
from pdf_generator import generate_pdf


""" Function to regularly update Date and Time in environment variable """
def clock(*args):
    now = datetime.now()
    date = datetime.strftime(now, '%d/%m/%Y')
    time = datetime.strftime(now, '%H:%M:%S')
    os.environ['DATE'] = date
    os.environ['TIME'] = time

Clock.schedule_interval(clock, 1)


""" Class to update Date and time in kivy screens """
class TikTok():
    def __init__(self) -> None:
        Clock.schedule_interval(self.tik_tok, 1)

    def tik_tok(self, *args) -> None:
        self.ids.calendar.text = os.environ.get('DATE')
        self.ids.clock.text = os.environ.get('TIME')


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


""" ⦿ Callback function for UART data incoming
        • Validate the raw data
        • Extract channels
        • Calculate original value from raw data
        • Pass values to subscribed functions
 """
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
uart.onDataIncoming = uart_data_incoming
time.sleep(0.1)
# connect and start reading the UART after loading the kv builder file:
    # uart.connect()
    # uart.read_raw()


class KeyboardManager():
    """
    A class to manage virtual keyboard and input assist.

    ...

    Attributes
    ----------
    None

    Methods
    -------
    set_input_focused_callback():
        Iterate widgets of screen by ID provided and bind focus event of the widget with callback function.
    """

    def __init__(self) -> None:
        self.__input = None
        self.input_assist = None
        self.__keyboard = Window.request_keyboard(
            self._keyboard_close, self)
        if self.__keyboard.widget:
            # ['azerty', 'de', 'fr_CH', 'de_CH', 'qwertz', 'en_US', 'qwerty']
            self.__keyboard.widget.layout = 'qwerty'

        print("[KEYBOARD]", self.__keyboard.widget.available_layouts.keys())
        self.set_input_focused_callback()

    @mainthread
    def set_input_focused_callback(self):
        for widget in self.ids.values():
            if isinstance(widget, TextInput):
                widget.bind(focus=self.input_focused_callback)

    def input_focused_callback(self, widget, is_focused, *args):
        if is_focused:
            if (widget.input_filter == 'int'):
                self.__keyboard.widget.layout = 'numeric.json'
            else:
                self.__keyboard.widget.layout = 'qwerty'

            self.__input = widget
            self.input_assist = TextInput(
                pos_hint={'x': 0, 'y': 0.48},
                size_hint=(1, 0.1),
                halign='center',
                text=widget.text,
                hint_text=widget.hint_text,
                input_filter=widget.input_filter,
                multiline=widget.multiline
            )
            self.input_assist.focus = 1
            self.input_assist.bind(focus=self.close_input_assist)
            self.add_widget(self.input_assist)

    def close_input_assist(self, widget, is_focused):
        if is_focused:
            return
        if self.__input:
            self.__input.text = self.input_assist.text
        self.remove_widget(self.input_assist)

    def _keyboard_close(self):
        pass


class GPIOManager():
    def __init__(self) -> None:
        """ Set up GPIO """
        print("[GPIO]:", "Initializing pins...")
        self.GPIO_UP = 17
        self.GPIO_DOWN = 27
        self.GPIO_FAST = 22
        self.GPIO_SLOW = 23
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.GPIO_UP, GPIO.OUT)
        GPIO.setup(self.GPIO_DOWN, GPIO.OUT)
        GPIO.setup(self.GPIO_FAST, GPIO.OUT)
        GPIO.setup(self.GPIO_SLOW, GPIO.OUT)

    def actuate_gpio(self, gpio, state):
        GPIO.output(gpio, state)
        print("[GPIO]:", gpio, "=>", state)


class OutputManager():
    ''' Class to store Test data and associated paths (graphs, pdf, excel, etc.) '''
    def __init__(self) -> None:
        self.output_type_multi = False
        self.output_datetime = None
        self.output_machine_number = None
        self.output_lot_number = None
        self.output_test_number = None
        self.output_invoice_number = None
        self.output_remarks = None
        self.canvas_path = None
        self.log_path = None
        self.pdf_path = None
        self.excel_path = None
        self.customer_details = {}
        self.product_details = {}

OUTPUT_MGR = OutputManager()


"""
    Class to manage Splash Screen
"""
class WindowSplash(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        Timer(5, self.end_splash).start()

    def end_splash(self):
        self.manager.current = 'layout_login'
        # self.manager.current = 'layout_trial'
        

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
class WindowHome(Screen, TikTok):
    def __init__(self, **kw):
        super().__init__(**kw)
        
        self.enable_operate_buttons(1)
        uart_channel_subscribe(self.update_reading_fom_uart)

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
        pass
        # self.ids.button_operate_up.disabled = disabled
        # self.ids.button_operate_fast.disabled = disabled
        # self.ids.button_operate_slow.disabled = disabled
        # self.ids.button_operate_down.disabled = disabled

    def update_reading_fom_uart(self, info, *args):
        print("\t", info)
        self.ids.label_load.text = format(info.get('ch1', 0), '.2f')
        self.ids.label_displacement.text = format(info.get('ch3', 0), '.3f')


"""
    Class to manage Test Config 1 Screen
"""
class WindowTC1(Screen, KeyboardManager, TikTok):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.test_id = 0
        # Timer(1, self.fetch_next_id).start()
        # Clock.schedule_once(self.fetch_next_id, 0)

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
        conn = sqlite3.connect('./data.db')
        sql = f''' INSERT OR IGNORE INTO Tests VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) '''
        print(sql)
        cur = conn.cursor()
        cur.execute(sql, (OUTPUT_MGR.output_test_number, OUTPUT_MGR.output_machine_number, OUTPUT_MGR.output_lot_number, OUTPUT_MGR.output_invoice_number,
            OUTPUT_MGR.customer_details.get('code', ''), OUTPUT_MGR.product_details.get('code', ''), OUTPUT_MGR.output_datetime, OUTPUT_MGR.output_remarks, 
            OUTPUT_MGR.canvas_path, OUTPUT_MGR.log_path, OUTPUT_MGR.pdf_path, OUTPUT_MGR.excel_path)
        )
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
        # self.ids.label_product_description.text = record[2]
        # self.ids.label_product_min.text = str(record[3])
        # self.ids.label_product_max.text = str(record[4])
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

    def submit(self):
        OUTPUT_MGR.customer_details['code'] = self.ids.spinner_master.text
        OUTPUT_MGR.customer_details['name'] = self.ids.label_name.text
        OUTPUT_MGR.product_details['code'] = self.ids.spinner_product_master.text
        OUTPUT_MGR.product_details['name'] = self.ids.label_product_name.text
        OUTPUT_MGR.output_datetime = datetime.now()
        OUTPUT_MGR.output_machine_number = self.ids.input_mid.text
        OUTPUT_MGR.output_lot_number = self.ids.input_lot.text
        OUTPUT_MGR.output_test_number = self.ids.label_id.text
        OUTPUT_MGR.output_invoice_number = self.ids.input_iid.text
        OUTPUT_MGR.output_remarks = self.ids.input_remarks.text
        print(OUTPUT_MGR.__dict__)
        self.save_to_db()
        self.manager.current = 'layout_testing'


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
class WindowTesting(Screen, Widget, TikTok):
    def __init__(self, **kw):
        super().__init__(**kw)
        
        self.is_graph_live = False
        self.graph = None
        self.graph_copy = None
        self.plot = None
        # plots added while ploting graph from multiple tests log
        self.plots = []
        
        self.generate_graph()
        
        uart_channel_subscribe(self.update_graph_fom_uart)

    @mainthread
    def generate_graph(self):
        self.graph = self.ids['graph_test']
        self.plot = LinePlot(line_width=2, color=[66/255, 245/255, 197/255, 1])
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
            pass#return
        self.plot.points.append((disp, load))
        # auto scaling
        load_padding = load / 10
        self.graph.xmax = max(self.graph.xmax, disp + 1)
        self.graph.ymax = max(self.graph.ymax, load + load_padding)
        self.graph.ymin = min(self.graph.ymin, load - load_padding)
        # tick adjustment
        self.graph.x_ticks_major = self.graph.xmax
        self.graph.y_ticks_major = self.graph.ymax

    def update_graph_from_log(self, test_ids):
        selected_tests =  []
        conn = sqlite3.connect('./data.db')
        cur = conn.cursor()
        for test_id in test_ids:
            sql = f'''SELECT * FROM Tests WHERE id=?;'''
            print(sql, (test_id,))
            try:
                cur.execute(sql, (test_id,))
            except sqlite3.OperationalError as e:
                print(e)
            else:
                row = cur.fetchone() or (test_id, *['' for i in range(11)])
                print(row)
                selected_tests.append(row)
        
        self.reset_graph()
        x_max = 1
        y_max = 1
        y_min = 0
        for test_data in selected_tests:
            log_file = test_data[9]
            print(log_file)
            plot = LinePlot(line_width=2, color=[random(), random(), random(), 1])
            self.plots.append(plot)
            try:
                with open(log_file, 'r') as f:
                    raw_data = f.read()
                    print("[FILE]:", raw_data)
                    data = ast.literal_eval(raw_data or '[]')
            except FileNotFoundError:
                print("[FILE]:", "Not found")
            else:
                plot.points = data
                for tup in data:
                    x_max = max(x_max, tup[0])
                    y_max = max(y_max, tup[1])
                    y_min = min(y_min, tup[1])
            self.graph.add_plot(plot)
        # adjust graph scale and ticks
        self.graph.xmax = x_max + x_max / 10
        self.graph.ymax = y_max + y_max/ 10
        self.graph.ymin = y_min - y_min/ 10
        self.graph.x_ticks_major = x_max
        self.graph.y_ticks_major = y_max - y_min
        self.manager.current = 'layout_testing'

    def save_canvas(self, filepath):
        self.graph.export_to_png(filepath)
        print("[PNG]:", filepath)

    def control_graph(self):
        if self.ids.button_graph_control.text == "START":
            self.ids.button_graph_control.text = "STOP"
            self.ids.button_home.disabled = 1
            self.is_graph_live = True
        else:
            self.ids.button_graph_control.text = "START"
            self.ids.button_home.disabled = 0
            self.is_graph_live = False
            timestamp = int(time.time())
            OUTPUT_MGR.canvas_path = f'/tmp/canvas-{timestamp}.png'
            OUTPUT_MGR.log_path = f'/tmp/graph-{timestamp}.txt'
            print(OUTPUT_MGR.__dict__)
            # Save graph canvas as png
            self.graph.export_to_png(OUTPUT_MGR.canvas_path)
            # Save graph data as text file
            with open(OUTPUT_MGR.log_path, 'w') as f:
                f.write(str(self.plot.points))
            # Update 'Tests' database paths
            db_utils.update_test_paths(OUTPUT_MGR.output_test_number, canvas=OUTPUT_MGR.canvas_path, log_path=OUTPUT_MGR.log_path)
            self.manager.get_screen("layout_output").populate_output()
            self.manager.current = 'layout_output'

    def on_enter(self, *args):
        if OUTPUT_MGR.output_type_multi:
            # Save graph as png            
            OUTPUT_MGR.canvas_path = f'/tmp/canvas-{int(time.time())}.png'
            self.graph.export_to_png(OUTPUT_MGR.canvas_path)
            print("[PNG]:", OUTPUT_MGR.canvas_path)
            # Remove all plots from graph
            for plot in self.plots:
                self.graph.remove_plot(plot)
            self.manager.current = 'layout_output'

    def reset_graph(self):
        self.plot.points = []
 

"""
    Class to manage Test Config 3 Screen
"""
class WindowOutput(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

    def populate_output(self):
        self.ids.label_customer_code.text = OUTPUT_MGR.customer_details.get('code', '')
        self.ids.label_customer_name.text = OUTPUT_MGR.customer_details.get('name', '')
        self.ids.label_product_code.text = OUTPUT_MGR.product_details.get('code', '')
        self.ids.label_product_name.text = OUTPUT_MGR.product_details.get('name', '')
        self.ids.label_mid.text = OUTPUT_MGR.output_machine_number or ''
        self.ids.label_lot.text = OUTPUT_MGR.output_lot_number or ''
        self.ids.label_iid.text = OUTPUT_MGR.output_invoice_number or ''
        self.ids.label_test.text = OUTPUT_MGR.output_test_number or ''
        self.ids.label_date.text = (OUTPUT_MGR.output_datetime or datetime.now()).strftime('%Y/%m/%d')
        self.ids.label_time.text = (OUTPUT_MGR.output_datetime or datetime.now()).strftime('%H:%M:%S')
        self.ids.graph_sample.source = OUTPUT_MGR.canvas_path

    def save_as_pdf(self):
        pdf_file_name = generate_pdf(OUTPUT_MGR)
        OUTPUT_MGR.pdf_path = pdf_file_name
        db_utils.update_test_paths(OUTPUT_MGR.output_test_number, pdf_path=pdf_file_name)

    def save_as_excel(self):
        pass

    def on_enter(self, *args):
        if OUTPUT_MGR.output_type_multi:
            self.ids.graph_sample.source = OUTPUT_MGR.canvas_path

    def on_leave(self, *args):
        OUTPUT_MGR.__init__()


"""
    Class to manage Calibration Screen
"""
class WindowCalibration(Screen, KeyboardManager):
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

        uart_channel_subscribe(self.adc_read_fom_uart)

    @mainthread
    def sync_data_from_db(self):
        ch1_calibration_data = db_utils.fetch_calibration_for_channel('ch1') 
        self.ids.ch1_decimal_point.text = str(ch1_calibration_data[1])
        self.ids.ch1_resolution.text = str(ch1_calibration_data[2])
        self.ids.ch1_max_capacity.text = str(ch1_calibration_data[3])
        self.ids.ch1_cal_capacity.text = str(ch1_calibration_data[4])
        ch3_calibration_data = db_utils.fetch_calibration_for_channel('ch3') 
        self.ids.ch3_decimal_point.text = str(ch3_calibration_data[1])
        self.ids.ch3_resolution.text = str(ch3_calibration_data[2])
        # self.ids.ch3_cal_span.text = str(ch3_calibration_data[6])
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

        cal_display_label = {
            self.channel1: {self.process_cal: 'label_ch1_cal_zero', self.process_span: 'label_ch1_cal_span'},
            self.channel2: {self.process_cal: 'label_ch2_cal_zero', self.process_span: 'label_ch2_cal_span'},
            self.channel3: {self.process_cal: 'label_ch3_cal_zero', self.process_span: 'label_ch3_cal_span'},
        }[self.cal_channel][self.cal_process]
        self.ids[cal_display_label].text = str(average_adc_reading)

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
        ch3_decimal_point = self.ids.ch3_decimal_point.text
        ch3_resolution = self.ids.ch3_resolution.text
        # ch3_cal_span = self.ids.ch3_cal_span.text
        ch3_cal_capacity = self.ids.ch3_cal_capacity.text
        ch3_max_capacity = self.ids.ch3_max_capacity.text

        db_utils.update_calibration_for_channel('ch1', decimal=ch1_decimal_point, resolution=ch1_resolution, max_capacity=ch1_max_capacity, cal_capacity=ch1_cal_capacity)
        ch1_calculator.set_parameters()
        db_utils.update_calibration_for_channel('ch3', decimal=ch3_decimal_point, resolution=ch3_resolution, max_capacity=ch3_max_capacity, cal_capacity=ch3_cal_capacity)
        ch3_calculator.set_parameters()

    def reset_screen(self):
        inputs = [self.ids.ch1_decimal_point, self.ids.ch1_resolution, self.ids.ch1_max_capacity,
            self.ids.ch1_cal_capacity, self.ids.ch3_decimal_point, self.ids.ch3_resolution,
            self.ids.ch3_cal_capacity, self.ids.ch3_max_capacity]
        for input in inputs:
            input.text = ""


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
    Class to manage Customer entry Screen
"""
class WindowCustomerEntry(Screen, KeyboardManager):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.fetch_customer_list()

    @mainthread
    def fetch_customer_list(self):
        conn = sqlite3.connect('./data.db')
        sql = f'''SELECT code FROM Customers;'''
        print(sql)
        cur = conn.cursor()
        try:
            cur.execute(sql)
        except sqlite3.OperationalError as e:
            print(e)
        else:
            rows = cur.fetchall() or []
            self.ids.spinner_code.values = []
            self.ids.spinner_code.values = [str(row[0]) for row in rows]

    def save(self):
        code = self.ids.spinner_code.text
        name = self.ids.input_name.text
        address = self.ids.input_address.text
        city = self.ids.input_city.text
        pin = self.ids.input_pin.text
        state = self.ids.input_state.text
        tel1 = self.ids.input_tel1.text
        tel2 = self.ids.get('input_tel2', {'text': ''})['text']
        mob = self.ids.input_mob.text
        email = self.ids.input_email.text

        if not code or not name or not address or not city or not pin or not state or not email:
            print("[CUSTOMER ENTRY]:", "data missing")
            return

        conn = sqlite3.connect('./data.db')
        cur = conn.cursor()
        sql = 'INSERT OR IGNORE INTO Customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
        cur.execute(sql, (code, name, address, city, pin, state, tel1, tel2, mob, email))
        conn.commit()

        self.ids.spinner_code.disabled = False

    def edit(self):
        self.ids.spinner_code.disabled = False

    def delete(self):
        code = self.ids.spinner_code.text
        conn = sqlite3.connect('./data.db')
        cur = conn.cursor()
        sql = 'DELETE FROM Customers where code=?;'
        cur.execute(sql, (code,))
        conn.commit()
        try:
            self.ids.spinner_code.values.remove(code)
            self.ids.spinner_code.text = self.ids.spinner_code.values[0]
        except (ValueError, IndexError):
            self.ids.spinner_code.text = '<select customer code>'

    def new(self):
        conn = sqlite3.connect('./data.db')
        sql = f'''SELECT code FROM Customers ORDER BY code DESC LIMIT 1;'''
        print(sql)
        cur = conn.cursor()
        try:
            cur.execute(sql)
        except sqlite3.OperationalError as e:
            print(e)
        else:
            row = cur.fetchone() or (0,)
            next_id = str(int(row[0]) + 1).zfill(3)
            spinner = self.ids.spinner_code
            if not next_id in spinner.values:
                spinner.values.append(next_id)
                spinner.text = spinner.values[-1]
            spinner.disabled = True

    def populate_data(self, code):
        conn = sqlite3.connect('./data.db')
        sql = f'''SELECT * FROM Customers WHERE code=?;'''
        print(sql)
        cur = conn.cursor()
        try:
            cur.execute(sql, (code,))
        except sqlite3.OperationalError as e:
            print(e)
        else:
            row = cur.fetchone() or (code, '', '', '', '', '', '', '', '', '')
            print(row)
            # self.ids.input_code.text = row[0]
            self.ids.input_name.text = row[1]
            self.ids.input_address.text = row[2]
            self.ids.input_pin.text = row[3]
            self.ids.input_city.text = row[4]
            self.ids.input_state.text = row[5]
            self.ids.input_tel1.text = row[6]
            # self.ids.input_tel2.text = row[7]
            self.ids.input_mob.text = row[8]
            self.ids.input_email.text = row[9]


class WindowProductEntry(Screen, KeyboardManager):
    """ Class to manage Product entry Screen """
    
    def __init__(self, **kw):
        super().__init__(**kw)
        self.fetch_product_list()

    @mainthread
    def fetch_product_list(self):
        conn = sqlite3.connect('./data.db')
        sql = f'''SELECT code FROM Materials;'''
        print(sql)
        cur = conn.cursor()
        try:
            cur.execute(sql)
        except sqlite3.OperationalError as e:
            print(e)
        else:
            rows = cur.fetchall() or []
            self.ids.spinner_code.values = []
            self.ids.spinner_code.values = [str(row[0]) for row in rows]

    def save(self):
        code = self.ids.spinner_code.text
        name = self.ids.input_name.text
        description = self.ids.input_description.text
        compression_value = self.ids.input_compression.text
        low_limit = self.ids.input_low_limit.text
        high_limit = self.ids.input_high_limit.text
        size = self.ids.input_size.text

        if not code or not name or not compression_value or not low_limit or not high_limit:
            print("[PRODUCT ENTRY]:", "data missing")
            return

        conn = sqlite3.connect('./data.db')
        cur = conn.cursor()
        sql = 'INSERT OR IGNORE INTO Materials VALUES (?, ?, ?, ?, ?, ?)'
        cur.execute(sql, (code, name, description, low_limit, high_limit, compression_value))
        conn.commit()

    def edit(self):
        self.ids.spinner_code.disabled = False

    def delete(self):
        code = self.ids.spinner_code.text
        conn = sqlite3.connect('./data.db')
        cur = conn.cursor()
        sql = 'DELETE FROM Materials where code=?;'
        cur.execute(sql, (code,))
        conn.commit()
        try:
            self.ids.spinner_code.values.remove(code)
            self.ids.spinner_code.text = self.ids.spinner_code.values[0]
        except (ValueError, IndexError):
            self.ids.spinner_code.text = '<select product code>'

    def new(self):
        conn = sqlite3.connect('./data.db')
        sql = f'''SELECT code FROM Materials ORDER BY code DESC LIMIT 1;'''
        print(sql)
        cur = conn.cursor()
        try:
            cur.execute(sql)
        except sqlite3.OperationalError as e:
            print(e)
        else:
            row = cur.fetchone() or (0,)
            next_id = str(int(row[0]) + 1).zfill(3)
            spinner = self.ids.spinner_code
            if not next_id in spinner.values:
                spinner.values.append(next_id)
                spinner.text = spinner.values[-1]
            spinner.disabled = True

    def populate_data(self, code):
        conn = sqlite3.connect('./data.db')
        sql = f'''SELECT * FROM Materials WHERE code=?;'''
        print(sql)
        cur = conn.cursor()
        try:
            cur.execute(sql, (code,))
        except sqlite3.OperationalError as e:
            print(e)
        else:
            row = cur.fetchone() or (code, '', '', '', '', '', '', '', '', '')
            print(row)
            self.ids.input_name.text = str(row[1])
            self.ids.input_description.text = str(row[2])
            self.ids.input_compression.text = ''    #  str(row[3])
            self.ids.input_low_limit.text = str(row[3])
            self.ids.input_high_limit.text = str(row[4])
            self.ids.input_size.text = str(row[5])


class WindowTrial(Screen):
    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.add_table()

    @mainthread
    def add_table(self):
        self.data_tables = MDDataTable(
            use_pagination=True,
            check=True,
            rows_num=4,
            pos_hint={'x': 0.05, 'y': 0.35},
            size_hint=(0.9, 0.6),
            background_color_selected_cell="#00987a",
            column_data=[
                ("No.", dp(10)),
                ("#Test", dp(20)),
                ("Date", dp(30), self.sort_on_signal),
                ("Time", dp(30)),
                ("Cust/Vend Code", dp(30)),
                ("Cust/Vend Name", dp(50), self.sort_on_schedule),
            ],
            row_data=[
                (
                    "1",
                    ("alert", [255 / 256, 165 / 256, 0, 1], "No Signal"),
                    "Astrid: NE shared managed",
                    "Medium",
                    "Triaged",
                    "0:33",
                )
            ],
            sorted_on="Schedule",
            sorted_order="ASC",
            elevation=2,
        )
        # self.data_tables.bind(on_row_press=self.on_row_press)
        self.data_tables.bind(on_check_press=self.on_check_press)
        self.add_widget(self.data_tables)
        self.populate_data_table()

    def get_checked_indices(self):
        cols_num = len(self.data_tables.column_data)
        row_num = len(self.data_tables.row_data)
        checked_indices = []
        for i in reversed(range(row_num)):
            cell_row = self.data_tables.table_data.view_adapter.get_visible_view(i*cols_num)
            if cell_row.ids.check.state != 'normal':
                checked_indices.append(i)
        return checked_indices

    def delete_rows(self):
        checked_indices = self.get_checked_indices()
        for index in checked_indices:
            print("[DELETE]:", self.data_tables.row_data[index])
            self.data_tables.row_data.pop(index)

    def populate_data_table(self):
        conn = sqlite3.connect('./data.db')
        sql = f'''SELECT * FROM Tests; '''
        print(sql)
        cur = conn.cursor()
        try:
            cur.execute(sql)
        except sqlite3.OperationalError as e:
            print(e)
        else:
            rows = cur.fetchall() or []
            print(rows)
            self.data_tables.row_data = []
            for row in rows:
                self.data_tables.row_data.append(row[:6])
            print(self.data_tables.__dict__.keys())
            return rows

    def generate_report(self):
        checked_indices = self.get_checked_indices()
        checked_ids = [self.data_tables.row_data[i][0] for i in checked_indices]
        OUTPUT_MGR.output_type_multi = True
        self.manager.get_screen('layout_testing').update_graph_from_log(checked_ids)

    def sort_on_signal(self, data):
        return zip(*sorted(enumerate(data), key=lambda l: l[1][2]))

    def sort_on_schedule(self, data):
        return zip(
            *sorted(
                enumerate(data),
                key=lambda l: sum(
                    [
                        int(l[1][-2].split(":")[0]) * 60,
                        int(l[1][-2].split(":")[1]),
                    ]
                ),
            )
        )

    def sort_on_team(self, data):
        return zip(*sorted(enumerate(data), key=lambda l: l[1][-1]))

    def on_check_press(self, instance_table, current_row):
        '''Called when the check box in the table row is checked.'''
        pass

    def on_row_press(self, instance_table, instance_row):
        pass

"""
    Class to manage all screens
"""
class WindowManager(ScreenManager):
    pass



# class CTControlApp(App, GPIOManager):
class CTControlApp(MDApp, GPIOManager):
    def build(self):
        # Window.clearcolor = (205/255, 205/255, 205/255, 1)
        Window.bind(on_request_close=self.on_request_close)
        
        try:
            # Load kv builder file
            kv = Builder.load_file('launcher.kv')
        except (SyntaxError, FactoryException) as e:
            print("======================")
            print("E X I T I N G . . .")
            print("error loading kv file.", e)
            print("======================")
            self.on_request_close()
            sys.exit(1)
        else:
            # connect and start reading from UART
            uart.connect()
            uart.read_raw()
        return kv

    def on_request_close(self, *args, **kwargs):
        if os.environ.get('terminate'):
            return
        print("\033[33m", "GUI quit signal received. Stopping backend...", "\033[0m")
        os.environ['terminate'] = '1'
        uart.halt = True
        GPIO.cleanup()


application = CTControlApp()
application.run()
application.on_request_close()
