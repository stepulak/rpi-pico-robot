import socket
import network
from machine import Pin, PWM

led = Pin("LED", Pin.OUT)
led.high()

DUTY_MAX=65535

class Motor():
    def __init__(self, p1, p2):
        self.p1 = PWM(Pin(p1, Pin.OUT))
        self.p2 = PWM(Pin(p2, Pin.OUT))
        self.p1.freq(50)
        self.p2.freq(50)
        self.velocity = DUTY_MAX

    def stop(self):
        self.p1.duty_u16(0)
        self.p2.duty_u16(0)

    def backward(self):
        self.stop()
        self.p1.duty_u16(self.velocity)
        self.p2.duty_u16(0)

    def forward(self):
        self.stop()
        self.p1.duty_u16(0)
        self.p2.duty_u16(self.velocity)

    def set_velocity_ratio(self, ratio):
        self.velocity = max(0, min(DUTY_MAX, int(ratio * DUTY_MAX)))


class MovementType():
    FWD = 1
    RWD = 2
    AWD = 3


class Direction():
    NONE = 0
    FORWARD = 1
    BACKWARD = 2
    LEFT = 4
    RIGHT = 8


class Movement():
    def __init__(self):
        self.motors = {
            Direction.RIGHT | Direction.BACKWARD: Motor(20, 21),
            Direction.RIGHT | Direction.FORWARD: Motor(18, 19),
            Direction.LEFT | Direction.BACKWARD: Motor(10, 11),
            Direction.LEFT | Direction.FORWARD: Motor(12, 13),
        }
        self.movement_type = MovementType.AWD
        self.direction = Direction.NONE

    def forward(self):
        if self.direction != Direction.FORWARD:
            self.stop()
        self.direction = Direction.FORWARD
        if self.movement_type & MovementType.FWD:
            self.motors[Direction.RIGHT | Direction.FORWARD].forward()
            self.motors[Direction.LEFT | Direction.FORWARD].forward()
        if self.movement_type & MovementType.RWD:
            self.motors[Direction.LEFT | Direction.BACKWARD].forward()
            self.motors[Direction.RIGHT | Direction.BACKWARD].forward()

    def backward(self):
        if self.direction != Direction.BACKWARD:
            self.stop()
        self.direction = Direction.BACKWARD
        if self.movement_type & MovementType.FWD:
            self.motors[Direction.RIGHT | Direction.FORWARD].backward()
            self.motors[Direction.LEFT | Direction.FORWARD].backward()
        if self.movement_type & MovementType.RWD:
            self.motors[Direction.LEFT | Direction.BACKWARD].backward()
            self.motors[Direction.RIGHT | Direction.BACKWARD].backward()

    def left(self):
        if self.direction != Direction.LEFT:
            self.stop()
        self.direction = Direction.LEFT
        self.motors[Direction.RIGHT | Direction.FORWARD].forward()
        self.motors[Direction.RIGHT | Direction.BACKWARD].forward()
        self.motors[Direction.LEFT | Direction.BACKWARD].backward()
        self.motors[Direction.LEFT | Direction.FORWARD].backward()

    def right(self):
        if self.direction != Direction.RIGHT:
            self.stop()
        self.direction = Direction.RIGHT
        self.motors[Direction.RIGHT | Direction.FORWARD].backward()
        self.motors[Direction.RIGHT | Direction.BACKWARD].backward()
        self.motors[Direction.LEFT | Direction.BACKWARD].forward()
        self.motors[Direction.LEFT | Direction.FORWARD].forward()

    def stop(self):
        for motor in self.motors.values():
            motor.stop()
            motor.set_velocity_ratio(1)

    def set_movement_type(self, mtype):
        self.stop()
        self.movement_type = mtype


movement = Movement()


wlan = network.WLAN(network.AP_IF)
wlan.config(essid="xxx", password="xpasswordx")
wlan.active(True)


class PicoHttpServer():
    def __init__(self):
        self.methods = {}

    def register_method(self, path, method):
        self.methods[path] = method

    @staticmethod
    def get_path_from_request(req):
        req = req.lstrip("GET ")
        path_end = req.find(" ")
        return req[:(path_end if path_end >= 0 else len(req))]

    @staticmethod
    def send_response(cl, status, msg=""):
        cl.send(f"HTTP/1.1 {status}\r\nContent-Type: text/html\r\n\r\n")
        cl.send(msg.encode())
        cl.close()

    def run(self):
        addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(addr)
        sock.listen(1)

        print(f"running server on {addr}:80")
        try:
            while True:
                cl, addr = sock.accept()
                req = cl.recv(4096).decode("utf-8")
                print("got request")
                if not req.startswith("GET /"):
                    print("invalid method")
                    PicoHttpServer.send_response(cl, "405 Method Not Allowed")
                    continue
                path = PicoHttpServer.get_path_from_request(req)
                print(f"path: {path}")
                if path not in self.methods:
                    print("path not registered")
                    PicoHttpServer.send_response(cl, "404 Not Found")
                    continue
                status, msg = self.methods[path]()
                PicoHttpServer.send_response(cl, status, msg)
        except Exception as e:
            cl.close()
            print(f"exception caught {e}")

        sock.close()


html = r"""
<html>
<body>
    <style>
        .filled {
            width: 100%;
            height: 100%;
        }
        .optgroup {
            font-size: 6vh;
            height: 33%;
            text-align: center;
        }
    </style>
    <h2 style="text-align:center">Controller</h2>
    <script>
        let interval = null;
        function buttodown(id) {
            const input = document.getElementById(id);
            input.style.background = "grey";
            fetch("/" + id);
            clearInterval(interval);
            interval = setInterval(() => {
                fetch("/" + id);
            }, 200);
        }
        function buttonup() {
            const inputs = document.getElementsByTagName("input");
            for (const input of inputs) {
                    input.style.background = "";
            }
            fetch("/stop");
            clearInterval(interval);
            interval = null;
        }
        // create control table
        const tbl = document.createElement("table");
        tbl.style.cssText = "width:70%;height:50%;margin-left:auto;margin-right:auto;";
        const labels = [null,"forward",null,"left",null,"right",null,"back",null];
        for (let rows = 0; rows < 3; rows++) {
            const tr = tbl.insertRow();
            for (let cols = 0; cols < 3; cols++) {
                const th = tr.insertCell();
                const label = labels[rows * 3 + cols];
                if (!label) {
                    continue;
                }
                const input = document.createElement("input");
                input.id = label;
                input.className = "filled";
                input.setAttribute("id", label);
                input.setAttribute("type", "button");
                input.setAttribute("value", label.toUpperCase());
                input.setAttribute("onpointerdown", "buttodown('" + label +"')");
                th.appendChild(input);
            }
        }
        document.body.appendChild(tbl);
        document.addEventListener("pointerup", buttonup);
        // wheel switcher
        function wheelswitch() {
            const select = document.getElementById("driveselect");
            if (select.value.length > 0) {
                fetch("/" + select.value.toLowerCase());
            }
        }
    </script>
    <div style="text-align:center; margin-top: 25px">
        <form>
            <select id="driveselect" size="3" style="width:120px;height:200px">
                <option class="optgroup" selected>AWD</option>
                <option class="optgroup">FWD</option>
                <option class="optgroup">RWD</option>
            </select>
        </form>
        <input type="button" onclick="wheelswitch()" value="Switch wheel drive!"/>
    </div>
</body>
</html>
"""


def awd():
    movement.set_movement_type(MovementType.AWD)
    return "200 OK", ""


def fwd():
    movement.set_movement_type(MovementType.FWD)
    return "200 OK", ""


def rwd():
    movement.set_movement_type(MovementType.RWD)
    return "200 OK", ""


def stop():
    movement.stop()
    return "200 OK", ""


def forward():
    movement.forward()
    return "200 OK", ""


def backward():
    movement.backward()
    return "200 OK", ""


def left():
    movement.left()
    return "200 OK", ""


def right():
    movement.right()
    return "200 OK", ""


p = PicoHttpServer()
p.register_method("/", lambda: ("200 OK", html))
p.register_method("/awd", awd)
p.register_method("/fwd", fwd)
p.register_method("/rwd", rwd)
p.register_method("/stop", stop)
p.register_method("/forward", forward)
p.register_method("/back", backward)
p.register_method("/left", left)
p.register_method("/right", right)

p.run()
