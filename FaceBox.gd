extends Control

var active := false
var box_rect := Rect2()
var box_color := Color("#00e87a")

func _draw() -> void:
	if not active:
		return
	draw_rect(box_rect, box_color, false, 1.5)
	var r := box_rect
	var l := 12
	for corner in [
		r.position,
		r.position + Vector2(r.size.x, 0),
		r.position + Vector2(0, r.size.y),
		r.position + r.size
	]:
		var sx := 1 if corner.x == r.position.x else -1
		var sy := 1 if corner.y == r.position.y else -1
		draw_line(corner, corner + Vector2(sx * l, 0), box_color, 2)
		draw_line(corner, corner + Vector2(0, sy * l), box_color, 2)
