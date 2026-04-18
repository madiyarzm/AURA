extends TextureRect

## CameraFeed — polls /tmp/robot_frame.bin and /tmp/robot_meta.json
## written atomically by face_track.py each frame.
##
## Signals:
##   shm_connected()                    — files became readable
##   shm_disconnected()                 — files disappeared / stale
##   meta_updated(meta: Dictionary)     — new metadata available

signal shm_connected
signal shm_disconnected
signal meta_updated(meta: Dictionary)

const POLL_INTERVAL := 0.033   # ~30 fps
const W := 640
const H := 480
const FILE_FRAME := "/tmp/robot_frame.bin"
const FILE_META  := "/tmp/robot_meta.json"
const STALE_TIMEOUT := 2.0     # seconds before declaring disconnected

var _connected    := false
var _poll_timer   := 0.0
var _stale_timer  := 0.0
var _img          := Image.create(W, H, false, Image.FORMAT_RGB8)

func _ready() -> void:
	expand_mode  = TextureRect.EXPAND_IGNORE_SIZE
	stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED

func _process(delta: float) -> void:
	_poll_timer += delta
	if _poll_timer < POLL_INTERVAL:
		return
	_poll_timer = 0.0
	_poll(delta)

func _poll(delta: float) -> void:
	# ── Read meta ──────────────────────────────────────────────────────────────
	var mf := FileAccess.open(FILE_META, FileAccess.READ)
	if not mf:
		_stale_timer += delta
		if _connected and _stale_timer >= STALE_TIMEOUT:
			_connected = false
			emit_signal("shm_disconnected")
		return

	var json_str := mf.get_as_text().strip_edges()
	mf.close()

	if json_str.is_empty():
		_stale_timer += delta
		return

	var meta: Variant = JSON.parse_string(json_str)
	if typeof(meta) != TYPE_DICTIONARY:
		return

	# ── Read frame ─────────────────────────────────────────────────────────────
	var ff := FileAccess.open(FILE_FRAME, FileAccess.READ)
	if ff:
		var raw := ff.get_buffer(W * H * 3)
		ff.close()
		if raw.size() == W * H * 3:
			_img.set_data(W, H, false, Image.FORMAT_RGB8, raw)
			texture = ImageTexture.create_from_image(_img)

	# ── Signals ────────────────────────────────────────────────────────────────
	_stale_timer = 0.0
	if not _connected:
		_connected = true
		emit_signal("shm_connected")

	emit_signal("meta_updated", meta)
