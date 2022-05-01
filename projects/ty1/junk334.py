from machine import Pin, PWM
import time
i = 0
pwm0 = PWM(Pin(9))         # create PWM object from a pin
pwm0.freq(120)            # set PWM frequency from 1Hz to 40MHz
dir=False
while True:
    if not dir:
        pwm0.duty(i)             # set duty cycle from 0 to 1023 as a ratio duty/1023, (now 25%)
        i += 1
        if i > 1022:
            dir = True 
    else:
        pwm0.duty(i)
        i -= 1
        if i < 1:
            dir = False

    time.sleep(0.002)