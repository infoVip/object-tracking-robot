import json
import threading
import time

import RPi.GPIO as GPIO
import netifaces as ni
import pigpio
from motor_controller import QuadMotorController
from pid import PID
from range_sensor import sensor
from server import Server

# from raspberry.motor_controller import QuadMotorController
# from raspberry.pid import PID
# from raspberry.range_sensor import sensor
# from raspberry.server import Server

status = ""

t = 0.1
fb_speed = 0
lr_speed = 0

x = 0
y = 0
width = 0
height = 0

x_min = 70
x_max = 200
maxArea = 800
minArea = 200

fb_pid = PID(target=6250, p=1, i=0.5, d=0.01)
lr_pid = PID(target=500, p=0.5, i=0, d=0.3)

motor_controller = QuadMotorController()

range_sensor_value = 100

no_object = "no_object"
run = 'Running'
STOP = 'Stopped'
MANUAL = 'Manual'

motor_status = 'stop'


def range_sensor_updater():
    global range_sensor_value
    print('range Sensor thread is running')
    pi = pigpio.pi()
    sonar = sensor(pi, trigger=23, echo=24)
    while True:
        try:
            sonar.trigger()
            time.sleep(0.1)
            cms, new = sonar.get_centimetres()
            if new:
                # range_sensor_value = cms
                range_sensor_value = 100
                # print('range : {}'.format(range_sensor_value))
        except Exception as e:
            print('range Sensor thread is stopped')
            print(e)
            sonar.cancel()
            pi.stop()


def reverse(m_speed=None):
    global motor_status
    if motor_status != 'forward':
        time.sleep(0.1)
    motor_status = 'forward'
    motor_controller.move_backward(back_speed=m_speed)
    # setLEDs(1, 0, 0, 1)
    # print('straight')


def forwards(m_speed=None):
    global motor_status
    if motor_status != 'forward':
        time.sleep(0.1)
    motor_status = 'forward'
    if range_sensor_value > 30:
        motor_controller.move_forward(forward_speed=m_speed)
    else:
        print('RANGE SENSOR : {} cm'.format(range_sensor_value))
    # setLEDs(0, 1, 1, 0)
    # print('straight')


def turnright(m_speed=None):
    global motor_status
    if motor_status != 'right':
        time.sleep(0.1)
    motor_status = 'right'
    motor_controller.move_right(right_speed=m_speed)
    # setLEDs(0, 0, 1, 1)
    # print('left')


def turnleft(m_speed=None):
    global motor_status
    if motor_status != 'left':
        time.sleep(0.1)
    motor_status = 'left'
    motor_controller.move_left(left_speed=m_speed)
    # setLEDs(1, 1, 0, 0)
    # print('right')


def stopall():
    global motor_status
    time.sleep(0.1)
    motor_controller.stopall()
    motor_status = 'stop'
    # setLEDs(1, 1, 1, 1)
    # print('stop')


def movement():
    global status, width, height, x_min, x_max, maxArea, minArea, x, y, fb_pid
    print("started")

    while True:
        message, address = server.receive()
        message = message.decode("utf-8")
        print("Got >>", message, " form : ", address)
        json_message = json.loads(message)

        if "x_min" in message:
            x_min = json_message.get("x_min")
            x_max = json_message.get("x_max")
            maxArea = json_message.get("maxArea")
            minArea = json_message.get("minArea")
            fb_pid.target = (minArea + maxArea) / 2
            print("Got Min and Max")

        if "status" in message:
            status = json_message.get("status")
            print("action: ", status)
            if status == STOP:
                # stop = True
                stopall()

        if "width" in message:
            x = json_message.get("x")
            y = json_message.get("y")
            width = json_message.get("width")
            height = json_message.get("height")
            print("x = {}, y = {}, width = {}, height = {}".format(x, y, width, height))
            if x == 0 and y == 0 and width == 0 and height == 0:
                status = no_object
            elif status == no_object:
                status = run

        FB = json_message.get("FB")

        LR = json_message.get("LR")

        manual_speed = 100
        # print FB + " " + LR + str(len(FB)) + str(len(LR))
        if FB == "F":
            forwards(m_speed=manual_speed)
            pass
        elif FB == "B":
            reverse(m_speed=manual_speed)
            pass

        elif LR == "L":
            turnleft(m_speed=manual_speed)
            pass

        elif LR == "R":
            turnright(m_speed=manual_speed)
            pass

        elif LR == "S" or FB == "S":
            # print 'stop'
            stopall()


# Helper Function
def percentage(part, whole):
    return 100 * float(part) / float(whole)


def map(value, istart, istop, ostart, ostop):
    return ostart + (ostop - ostart) * ((value - istart) / (istop - istart))


def auto_movement():
    global status, width, height, x_min, x_max, maxArea, minArea, x, y, fb_speed, fb_pid
    last_turn = 'L'
    no_object_loops = 0

    while True:
        if status == run:

            no_object_loops = 0

            area = width * height
            update = fb_pid.update(area)
            raw_speed = percentage(update, fb_pid.target)

            is_forward = raw_speed > 30
            is_backward = raw_speed < -30
            fb_speed = max(0, min(100, abs(int(raw_speed))))

            lr_update = lr_pid.update(x)
            lr_speed = percentage(lr_update, lr_pid.target)

            is_left = lr_speed > 30
            is_right = lr_speed < -30

            lr_speed = max(0, min(100, abs(int(lr_speed))))
            lr_speed = int(map(lr_speed, 0, 100, 0, 100))

            print('******************************')
            print('lr speed is :{} {} {}'.format(lr_speed, is_left, is_right))
            print('x is :{}'.format(x))
            print('******************************')
            # is_forward = area < minArea
            # is_backward = area > maxArea
            # speed = 100
            # print()
            # print('******************************')
            # print('fb speed is :{}'.format(fb_speed))
            # print('area is :{}'.format(area))
            # print('******************************')

            if is_left:
                turnleft(m_speed=lr_speed)
                x += 500 * (lr_speed / 100)
                # last_turn = 'L'
            elif is_right:
                turnright(m_speed=lr_speed)
                x -= 500 * (lr_speed / 100)
                # last_turn = 'R'
            elif lr_speed < 10:
                stopall()

            # motor_controller.stopall()
            #
            if is_forward:
                forwards(m_speed=fb_speed)
                area += 300 * (fb_speed / 100)
            elif is_backward:
                reverse(m_speed=fb_speed)
                area -= 300 * (fb_speed / 100)
            elif fb_speed < 10:
                stopall()

        elif status == no_object and False:
            if no_object_loops < 5:
                no_object_loops += 1
                if last_turn == 'R':
                    turnright()
                else:
                    turnleft()
                time.sleep(0.1)
                stopall()
                time.sleep(0.5)
        else:
            time.sleep(1)


if __name__ == '__main__':
    ip = ni.ifaddresses('wlan0')[ni.AF_INET][0]['addr']
    server = Server(host=ip)

    print('Server is online \nHost Name : {}:{}'.format(server.host_name, server.port))
    try:
        range_sensor_thread = threading.Thread(target=range_sensor_updater)
        movement_thread = threading.Thread(target=movement)
        auto_movement_thread = threading.Thread(target=auto_movement)
        # range_sensor_thread.start()
        movement_thread.start()
        auto_movement_thread.start()

        # range_sensor_thread.join()
        movement_thread.join()
        auto_movement_thread.join()

    finally:
        motor_controller.stopall()
        GPIO.cleanup()
        stopall()
