import machine
import time
#
led = machine.Pin(2, machine.Pin.OUT)
led.value(0)
for i in range(20):
    led.value(1)
    time.sleep(0.5)
    led.value(0)
    time.sleep(0.5)
    print('*')
    # here's johnny!
