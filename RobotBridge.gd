extends Node

## RobotBridge — Autoload singleton
## Connects to serial_bridge.py via TCP (localhost:6551),
## which forwards commands to the Arduino over Serial.

signal connection_changed(connected: bool)
signal command_sent(cmd: String)

var connected := false

const _HOST        := "127.0.0.1"
const _PORT        := 6551
const _DEBOUNCE_MS := 80   # collapse rapid slider events per axis
const _MAX_QUEUE   := 8    # max buffered commands while disconnected
const _RECONNECT_S := 3.0  # seconds between reconnect attempts

var _tcp:           StreamPeerTCP
var _queue:         Array[String] = []
var _pending_servo: Dictionary    = {}
var _debounce:      Timer
var _reconnect:     Timer
var _last_status:   int = -1

# --------------------------------------------------------------------------

func _ready() -> void:
	_debounce = Timer.new()
	_debounce.one_shot = true
	_debounce.timeout.connect(_flush_servo)
	add_child(_debounce)

	_reconnect = Timer.new()
	_reconnect.one_shot = true
	_reconnect.timeout.connect(_try_connect)
	add_child(_reconnect)

	_try_connect()

func _process(_delta: float) -> void:
	if not _tcp:
		return
	_tcp.poll()
	var status := _tcp.get_status()
	if status == _last_status:
		return
	_last_status = status
	match status:
		StreamPeerTCP.STATUS_CONNECTED:
			_set_connected(true)
			_pump()
		StreamPeerTCP.STATUS_NONE, StreamPeerTCP.STATUS_ERROR:
			_set_connected(false)
			_schedule_reconnect()

# --- Public API -----------------------------------------------------------

func send_expression(expr: String) -> void:
	# Map Godot button names → Arduino expression names
	var mapped: String = expr
	match expr:
		"neutral": mapped = "neutral_open"
		"blink":   mapped = "neutral_close"
	var cmd := "expr:" + mapped
	emit_signal("command_sent", cmd)
	_enqueue(cmd)

func send_servo(axis: String, angle: int) -> void:
	angle = clamp(angle, 0, 180)
	_pending_servo[axis] = angle
	if _debounce.is_stopped():
		_debounce.start(_DEBOUNCE_MS / 1000.0)

func center_servos() -> void:
	emit_signal("command_sent", "servo:center")
	_enqueue("servo:center")

# --- Internal -------------------------------------------------------------

func _try_connect() -> void:
	_tcp = StreamPeerTCP.new()
	_last_status = -1
	var err := _tcp.connect_to_host(_HOST, _PORT)
	if err != OK:
		push_warning("RobotBridge: connect_to_host error %d" % err)
		_schedule_reconnect()

func _schedule_reconnect() -> void:
	if _reconnect.is_stopped():
		_reconnect.start(_RECONNECT_S)

func _flush_servo() -> void:
	for axis in _pending_servo:
		var angle: int = int(_pending_servo[axis])
		# Arduino expects lowercase axis: servo:h:90 / servo:v:90
		var cmd := "servo:%s:%d" % [axis.to_lower(), angle]
		emit_signal("command_sent", cmd)
		_enqueue(cmd)
	_pending_servo.clear()

func _enqueue(cmd: String) -> void:
	while _queue.size() >= _MAX_QUEUE:
		_queue.pop_front()
	_queue.append(cmd)
	_pump()

func _pump() -> void:
	if not connected or _queue.is_empty():
		return
	while not _queue.is_empty():
		var cmd: String = _queue.pop_front()
		var err := _tcp.put_data((cmd + "\n").to_utf8_buffer())
		if err != OK:
			push_warning("RobotBridge: put_data error %d — disconnecting" % err)
			_set_connected(false)
			_schedule_reconnect()
			return

func _set_connected(value: bool) -> void:
	if connected != value:
		connected = value
		if connected:
			_reconnect.stop()
		emit_signal("connection_changed", connected)
