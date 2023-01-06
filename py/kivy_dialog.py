"""********************************************************
Author:         Akshay C P
Date:           06 Jan 2023
Description:    Script to popup dialog box using KivyMD
********************************************************"""

from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog

from threading import Timer

def null(*args, **kwargs):
    pass


class Confirm():
    def __init__(self):
        self.dialog = None
        self.primary_palette = "#00987a"

    def popup(self, text="Discard draft?", yes_btn_text="OK", no_btn_text="CANCEL", 
        yes_btn_cb=None, no_btn_cb=None, blocking=True):
        self.user_intervention = False
        yes_btn_cb = yes_btn_cb or null
        no_btn_cb = no_btn_cb or null

        def dialog_yes(*args):
            self.user_intervention = True
            self.dialog.dismiss()
            yes_btn_cb()
        
        def dialog_no(*args):
            self.user_intervention = True
            self.dialog.dismiss()
            no_btn_cb()

        self.dialog = MDDialog(
            text=text,
            buttons=[
                MDFlatButton(
                    text=yes_btn_text,
                    theme_text_color="Custom",
                    text_color=self.primary_palette,
                    on_release=dialog_yes
                ),
                MDRaisedButton(
                    text=no_btn_text,
                    theme_text_color="Custom",
                    text_color=self.primary_palette,
                    md_bg_color="#85edd9",
                    on_release=dialog_no
                ),
            ],
        )
        self.dialog.on_dismiss = lambda: not self.user_intervention and blocking
        self.dialog.open()


class Alert():
    def __init__(self):
        self.primary_palette = "#00987a"

    def popup(self, text="Alert", timeout=0, blocking=True) -> object:
        self.blocking = blocking
        self.system_intervention = False

        self.dialog = MDDialog(
            text=text,
        )
        self.dialog.on_dismiss = lambda: not (self.system_intervention or not blocking)
        self.dialog.open()
        if timeout: Timer(timeout, self.popdown).start()
        return self

    def popdown(self):
        self.system_intervention = True
        if self.dialog: 
            self.dialog.dismiss()
            self.dialog = None


if __name__ == '__main__':
    from kivymd.app import MDApp
    from kivy.uix.floatlayout import FloatLayout

    class Example(MDApp):
        def open_dialog(self, *args):
            Confirm().popup("Hello World", blocking=False)
            Alert().popup("Hello World", timeout=2, blocking=False)

        def build(self):
            btn = MDFlatButton(text="Open Dialog", pos_hint={'center_x': .5, 'center_y': .5},
                on_release=self.open_dialog)
            layout = FloatLayout()
            layout.add_widget(btn)
            return layout

    Example().run()