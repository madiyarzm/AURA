extends Control

## RobotUI — attached to RobotControl (root of RobotControl.tscn)

# ── Side panel ─────────────────────────────────────────────────────────────
@onready var _status_dot:      ColorRect = $MainLayout/SidePanel/SideMargin/SideVBox/StatusSection/StatusRow/StatusDot
@onready var _status_lbl:      Label     = $MainLayout/SidePanel/SideMargin/SideVBox/StatusSection/StatusRow/StatusLabel
@onready var _sub_status_lbl:  Label     = $MainLayout/SidePanel/SideMargin/SideVBox/StatusSection/SubStatusLabel

@onready var _dist_val:    Label = $MainLayout/SidePanel/SideMargin/SideVBox/MetricsSection/MetricsGrid/DistCard/DistCardBox/DistVal
@onready var _off_x_val:   Label = $MainLayout/SidePanel/SideMargin/SideVBox/MetricsSection/MetricsGrid/OffXCard/OffXCardBox/OffXVal
@onready var _servo_h_val: Label = $MainLayout/SidePanel/SideMargin/SideVBox/MetricsSection/MetricsGrid/ServoHCard/ServoHCardBox/ServoHVal
@onready var _servo_v_val: Label = $MainLayout/SidePanel/SideMargin/SideVBox/MetricsSection/MetricsGrid/ServoVCard/ServoVCardBox/ServoVVal

@onready var _btn_sad:     Button = $MainLayout/SidePanel/SideMargin/SideVBox/ExprSection/ExprGrid/BtnSad
@onready var _btn_angry:   Button = $MainLayout/SidePanel/SideMargin/SideVBox/ExprSection/ExprGrid/BtnAngry
@onready var _btn_neutral: Button = $MainLayout/SidePanel/SideMargin/SideVBox/ExprSection/ExprGrid/BtnNeutral
@onready var _btn_blink:   Button = $MainLayout/SidePanel/SideMargin/SideVBox/ExprSection/ExprGrid/BtnBlink

# ── Camera area ─────────────────────────────────────────────────────────────
@onready var _dist_label:      Label   = $MainLayout/CameraArea/DistLabel
@onready var _tracking_badge:  Label   = $MainLayout/CameraArea/TrackingBadge
@onready var _tap_zone:        Button  = $MainLayout/CameraArea/TapZone
@onready var _face_box:        Control = $MainLayout/CameraArea/FaceBox

# ── Test panel ───────────────────────────────────────────────────────────────
@onready var _test_panel:      PanelContainer = $TestPanel
@onready var _close_btn:       Button         = $TestPanel/TestMargin/TestVBox/TestHeader/CloseBtn

@onready var _bridge_dot:   ColorRect = $TestPanel/TestMargin/TestVBox/ConnectionSection/DotsRow/BridgeItem/BridgeDot
@onready var _arduino_dot:  ColorRect = $TestPanel/TestMargin/TestVBox/ConnectionSection/DotsRow/ArduinoItem/ArduinoDot
@onready var _camera_dot:   ColorRect = $TestPanel/TestMargin/TestVBox/ConnectionSection/DotsRow/CameraItem/CameraDot

@onready var _test_btn_sad:     Button  = $TestPanel/TestMargin/TestVBox/TestExprSection/TestExprGrid/TestBtnSad
@onready var _test_btn_angry:   Button  = $TestPanel/TestMargin/TestVBox/TestExprSection/TestExprGrid/TestBtnAngry
@onready var _test_btn_neutral: Button  = $TestPanel/TestMargin/TestVBox/TestExprSection/TestExprGrid/TestBtnNeutral
@onready var _test_btn_blink:   Button  = $TestPanel/TestMargin/TestVBox/TestExprSection/TestExprGrid/TestBtnBlink

@onready var _slider_h:   HSlider = $TestPanel/TestMargin/TestVBox/ServoTestSection/HRow/SliderH
@onready var _h_val_lbl:  Label   = $TestPanel/TestMargin/TestVBox/ServoTestSection/HRow/HValLbl
@onready var _slider_v:   HSlider = $TestPanel/TestMargin/TestVBox/ServoTestSection/VRow/SliderV
@onready var _v_val_lbl:  Label   = $TestPanel/TestMargin/TestVBox/ServoTestSection/VRow/VValLbl
@onready var _center_btn: Button  = $TestPanel/TestMargin/TestVBox/ServoTestSection/CenterBtn

@onready var _log_panel: RichTextLabel = $TestPanel/TestMargin/TestVBox/LogSection/LogPanel

# ── State ────────────────────────────────────────────────────────────────────
var _bridge: Node
var _active_expr_btn: Button = null
var _test_panel_open := false

const TEST_PANEL_WIDTH := 340.0
const COL_GREEN  := Color("#00e87a")
const COL_ORANGE := Color("#EF9F27")
const COL_RED    := Color("#E24B4A")
const COL_BLUE   := Color("#378ADD")
const COL_DIM    := Color("#E24B4A")  # camera disconnected default

var _style_expr_normal: StyleBoxFlat
var _style_expr_active: StyleBoxFlat

func _ready() -> void:
	_build_styles()

	_bridge = get_node_or_null("/root/RobotBridge")
	if _bridge:
		_bridge.connection_changed.connect(_on_connection_changed)
		_bridge.command_sent.connect(_on_command_sent)
		_on_connection_changed(_bridge.connected)
	else:
		_set_connection_dots(COL_RED, COL_RED, COL_DIM)
		_status_lbl.text = "DISCONNECTED"
		_status_dot.color = COL_RED

	# initial slider values (H center 80, V center 60 per Arduino defaults)
	_slider_h.value = 80
	_slider_v.value = 60
	_h_val_lbl.text = "80°"
	_v_val_lbl.text = "60°"

	# hide test panel off-screen (anchored right, offset_left = 0)
	_test_panel.offset_left = 0.0
	_test_panel.offset_right = TEST_PANEL_WIDTH

	# camera dot starts red (no camera feed yet)
	_camera_dot.color = COL_DIM

func _build_styles() -> void:
	_style_expr_normal = StyleBoxFlat.new()
	_style_expr_normal.bg_color = Color("#111111")
	_style_expr_normal.set_border_width_all(1)
	_style_expr_normal.border_color = Color("#1e1e1e")
	_style_expr_normal.set_corner_radius_all(4)

	_style_expr_active = StyleBoxFlat.new()
	_style_expr_active.bg_color = Color("#0a1520")
	_style_expr_active.set_border_width_all(2)
	_style_expr_active.border_color = COL_BLUE
	_style_expr_active.set_corner_radius_all(4)

# ── Expression buttons ────────────────────────────────────────────────────────

func _on_btn_sad_pressed() -> void:
	_send_expr("sad")

func _on_btn_angry_pressed() -> void:
	_send_expr("angry")

func _on_btn_neutral_pressed() -> void:
	_send_expr("neutral")

func _on_btn_blink_pressed() -> void:
	_send_expr("blink")

func _on_test_btn_sad_pressed() -> void:
	_send_expr("sad")

func _on_test_btn_angry_pressed() -> void:
	_send_expr("angry")

func _on_test_btn_neutral_pressed() -> void:
	_send_expr("neutral")

func _on_test_btn_blink_pressed() -> void:
	_send_expr("blink")

func _send_expr(expr: String) -> void:
	if _bridge:
		_bridge.send_expression(expr)
	_set_active_expr(_get_expr_btn(expr))
	log_cmd("expr:" + expr, _bridge != null)

func _get_expr_btn(expr: String) -> Button:
	match expr:
		"sad":     return _btn_sad
		"angry":   return _btn_angry
		"neutral": return _btn_neutral
		"blink":   return _btn_blink
	return _btn_neutral

func _set_active_expr(btn: Button) -> void:
	for b in [_btn_sad, _btn_angry, _btn_neutral, _btn_blink,
			  _test_btn_sad, _test_btn_angry, _test_btn_neutral, _test_btn_blink]:
		b.add_theme_stylebox_override("normal",  _style_expr_normal)
		b.add_theme_stylebox_override("focus",   _style_expr_normal)
		b.add_theme_stylebox_override("pressed", _style_expr_normal)
	# highlight both the main and test counterparts
	for b in [btn, _get_test_counterpart(btn)]:
		b.add_theme_stylebox_override("normal",  _style_expr_active)
		b.add_theme_stylebox_override("focus",   _style_expr_active)
		b.add_theme_stylebox_override("pressed", _style_expr_active)
	_active_expr_btn = btn

func _get_test_counterpart(btn: Button) -> Button:
	if btn == _btn_sad:     return _test_btn_sad
	if btn == _btn_angry:   return _test_btn_angry
	if btn == _btn_neutral: return _test_btn_neutral
	if btn == _btn_blink:   return _test_btn_blink
	return _test_btn_neutral

# ── Servo sliders ────────────────────────────────────────────────────────────

func _on_slider_h_changed(value: float) -> void:
	_h_val_lbl.text = "%d°" % int(value)
	if _bridge:
		_bridge.send_servo("H", int(value))

func _on_slider_v_changed(value: float) -> void:
	_v_val_lbl.text = "%d°" % int(value)
	if _bridge:
		_bridge.send_servo("V", int(value))

func _on_center_btn_pressed() -> void:
	if _bridge:
		_bridge.center_servos()
	_slider_h.value = 80
	_slider_v.value = 60
	log_cmd("servo:center", _bridge != null)

# ── Sweep buttons ────────────────────────────────────────────────────────────

func _on_sweep_pressed(cmd: String) -> void:
	if _bridge:
		_bridge._enqueue(cmd)
	log_cmd(cmd, _bridge != null)

# ── Test panel toggle ─────────────────────────────────────────────────────────

func _on_tap_zone_pressed() -> void:
	_toggle_test_panel()

func _on_close_btn_pressed() -> void:
	_close_test_panel()

func _toggle_test_panel() -> void:
	if _test_panel_open:
		_close_test_panel()
	else:
		_open_test_panel()

func _open_test_panel() -> void:
	_test_panel_open = true
	var tw := create_tween()
	tw.set_ease(Tween.EASE_OUT)
	tw.set_trans(Tween.TRANS_CUBIC)
	tw.tween_property(_test_panel, "offset_left", -TEST_PANEL_WIDTH, 0.25)
	tw.parallel().tween_property(_test_panel, "offset_right", 0.0, 0.25)

func _close_test_panel() -> void:
	_test_panel_open = false
	var tw := create_tween()
	tw.set_ease(Tween.EASE_OUT)
	tw.set_trans(Tween.TRANS_CUBIC)
	tw.tween_property(_test_panel, "offset_left", 0.0, 0.25)
	tw.parallel().tween_property(_test_panel, "offset_right", TEST_PANEL_WIDTH, 0.25)

# ── Bridge signals ────────────────────────────────────────────────────────────

func _on_connection_changed(is_connected: bool) -> void:
	if is_connected:
		_bridge_dot.color = COL_GREEN
		_status_dot.color = COL_GREEN
		_status_lbl.text = "CONNECTED"
		_status_lbl.add_theme_color_override("font_color", COL_GREEN)
	else:
		_bridge_dot.color = COL_RED
		_status_dot.color = COL_RED
		_status_lbl.text = "DISCONNECTED"
		_status_lbl.add_theme_color_override("font_color", COL_RED)

func _on_command_sent(cmd: String) -> void:
	log_cmd(cmd, true)

# ── State update (called externally from camera/tracking pipeline) ─────────────

func update_state(mode: String, tracking: bool, face_dist: float,
				  off_x: float, servo_h: int, servo_v: int, _expr: String) -> void:
	if mode == "tracking" and tracking:
		_status_dot.color = COL_GREEN
		_status_lbl.text = "TRACKING"
		_status_lbl.add_theme_color_override("font_color", COL_GREEN)
		_sub_status_lbl.text = "face locked"
		_sub_status_lbl.add_theme_color_override("font_color", Color("#1a4a2a"))
		_tracking_badge.text = "● TRACKING"
		_tracking_badge.add_theme_color_override("font_color", COL_GREEN)
	elif mode == "tracking" and not tracking:
		_status_dot.color = COL_ORANGE
		_status_lbl.text = "SEARCHING"
		_status_lbl.add_theme_color_override("font_color", COL_ORANGE)
		_sub_status_lbl.text = "no face detected"
		_sub_status_lbl.add_theme_color_override("font_color", COL_ORANGE)
		_tracking_badge.text = "◌ SEARCHING"
		_tracking_badge.add_theme_color_override("font_color", COL_ORANGE)
	else:
		_status_dot.color = COL_BLUE
		_status_lbl.text = "MANUAL"
		_status_lbl.add_theme_color_override("font_color", COL_BLUE)
		_sub_status_lbl.text = "direct control"
		_sub_status_lbl.add_theme_color_override("font_color", COL_BLUE)
		_tracking_badge.text = "◆ MANUAL"
		_tracking_badge.add_theme_color_override("font_color", COL_BLUE)

	_dist_val.text    = "%dcm" % int(face_dist)
	_off_x_val.text   = "%+.2f" % off_x
	_servo_h_val.text = "%d°" % servo_h
	_servo_v_val.text = "%d°" % servo_v
	_dist_label.text  = "%d cm" % int(face_dist)

	# keep sliders in sync when driven externally
	_slider_h.value = servo_h
	_slider_v.value = servo_v

# ── Log ───────────────────────────────────────────────────────────────────────

func log_cmd(cmd: String, ok: bool) -> void:
	var t := Time.get_time_string_from_system()
	var color := "#0a3a1a" if ok else "#1a3a5a"
	_log_panel.append_text("[color=%s]%s > %s[/color]\n" % [color, t, cmd])

func _set_connection_dots(bridge: Color, arduino: Color, camera: Color) -> void:
	_bridge_dot.color = bridge
	_arduino_dot.color = arduino
	_camera_dot.color = camera

func _set_camera_dot(ok: bool) -> void:
	_camera_dot.color = COL_GREEN if ok else COL_DIM

# ── Camera feed signals ───────────────────────────────────────────────────────

func _on_camera_shm_connected() -> void:
	_set_camera_dot(true)

func _on_camera_shm_disconnected() -> void:
	_set_camera_dot(false)

func _on_camera_meta_updated(meta: Dictionary) -> void:
	var tracking: bool  = meta.get("tracking", false)
	var dist: float     = meta.get("dist", 0.0)
	var off_x: float    = meta.get("off_x", 0.0)
	var servo_h: int    = meta.get("servo_h", 80)
	var servo_v: int    = meta.get("servo_v", 60)

	update_state("tracking", tracking, dist, off_x, servo_h, servo_v, "")
