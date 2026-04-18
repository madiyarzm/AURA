extends Control

func _draw() -> void:
	var c := get_rect().get_center()
	draw_line(c + Vector2(-12, 0), c + Vector2(12, 0), Color(1, 1, 1, 0.15), 1)
	draw_line(c + Vector2(0, -12), c + Vector2(0, 12), Color(1, 1, 1, 0.15), 1)
