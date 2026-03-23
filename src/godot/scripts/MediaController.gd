extends Node

var video_player: VideoStreamPlayer
var current_media_key: String = ""
var current_loop: bool = false
var current_media_path: String = ""


func _ready() -> void:
    video_player = VideoStreamPlayer.new()
    video_player.expand = true
    video_player.autoplay = false
    video_player.anchor_right = 1.0
    video_player.anchor_bottom = 1.0
    add_child(video_player)


func preload_media(media_rows: Array) -> Dictionary:
    return {"ok": true, "preloaded": media_rows.size()}


func play_video(media_key: String, media_path: String, loop_enabled: bool) -> Dictionary:
    current_media_key = media_key
    current_media_path = media_path
    current_loop = loop_enabled
    var ext: String = media_path.get_extension().to_lower()
    if ext not in ["ogv", "ogg"]:
        video_player.stop()
        video_player.stream = null
        return {"ok": false, "error": "unsupported_video_format", "path": media_path, "ext": ext}
    var stream := VideoStreamTheora.new()
    stream.file = media_path
    video_player.stream = stream
    if video_player.stream != null:
        video_player.play()
        return {"ok": true, "playback": status()}
    return {"ok": false, "error": "video_load_failed", "path": media_path}


func stop_video() -> Dictionary:
    video_player.stop()
    video_player.stream = null
    current_media_key = ""
    current_media_path = ""
    current_loop = false
    return {"ok": true, "playback": status()}


func pause_video() -> Dictionary:
    video_player.paused = true
    return {"ok": true, "playback": status()}


func status() -> Dictionary:
    return {
        "status": "playing" if video_player.is_playing() and not video_player.paused else "paused" if video_player.paused else "stopped",
        "mediaKey": current_media_key,
        "mediaPath": current_media_path,
        "loop": current_loop,
        "positionMs": int(video_player.stream_position * 1000.0),
    }
