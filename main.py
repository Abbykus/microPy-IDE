#!/usr/bin/python3
# -*- coding: utf-8 -*-
import time
import machine
led = machine.Pin(2, machine.Pin.OUT)
led.value(0)
for i in range(100):
    led.value(0)
    time.sleep(0.25)
    led.value(1)
    time.sleep(0.25)

