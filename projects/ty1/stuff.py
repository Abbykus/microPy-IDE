from machine import PWM, Pin
import time
i = 0
dir = False    
p=PWM(Pin(9, Pin.OUT), freq=600, duty=i)
while True:
    p.duty(i)
    #p1=PWM(Pin(2, Pin.OUT), freq=600, duty=i)
    time.sleep(0.001)
    if not dir:
        i += 1
        if i > 1023:
            dir = True 
            i = 1023
    else:
        i -= 1
        if i < 0:
            i = 0
            dir = False
