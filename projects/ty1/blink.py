import machine
import time
led = machine.Pin(2, machine.Pin.OUT)
led.value(0)
for i in range(20):
    led.value(True)
    time.sleep(0.25)
    led.value(False)
    time.sleep(0.25)
    print('i=', i)
    junk here
# the end my friend
print('i=', i+1)