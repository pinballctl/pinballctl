extends Node

var root: Control
var background_rect: ColorRect
var image_view: TextureRect
var video_player: VideoStreamPlayer
var message_wrap: CenterContainer
var message_box: VBoxContainer
var message_title: Label
var message_subtitle: Label
var current_media_key: String = ""
var current_loop: bool = false
var current_media_path: String = ""
var current_scene_key: String = "no_scene"
var current_scene_name: String = "No scene loaded"
var current_status: String = "stopped"
var pending_video_path: String = ""
var pending_video_key: String = ""
var pending_video_loop: bool = false


func _ready() -> void:
    root = Control.new()
    root.name = "MediaRoot"
    root.set_anchors_preset(Control.PRESET_FULL_RECT)
    root.mouse_filter = Control.MOUSE_FILTER_IGNORE
    add_child(root)

    background_rect = ColorRect.new()
    background_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
    background_rect.color = Color("000000")
    root.add_child(background_rect)

    image_view = TextureRect.new()
    image_view.set_anchors_preset(Control.PRESET_FULL_RECT)
    image_view.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
    image_view.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
    image_view.mouse_filter = Control.MOUSE_FILTER_IGNORE
    image_view.visible = false
    root.add_child(image_view)

    video_player = VideoStreamPlayer.new()
    video_player.expand = true
    video_player.autoplay = false
    video_player.loop = false
    video_player.set_anchors_preset(Control.PRESET_FULL_RECT)
    video_player.mouse_filter = Control.MOUSE_FILTER_IGNORE
    video_player.visible = false
    root.add_child(video_player)

    message_wrap = CenterContainer.new()
    message_wrap.set_anchors_preset(Control.PRESET_FULL_RECT)
    message_wrap.mouse_filter = Control.MOUSE_FILTER_IGNORE
    root.add_child(message_wrap)

    message_box = VBoxContainer.new()
    message_box.alignment = BoxContainer.ALIGNMENT_CENTER
    message_wrap.add_child(message_box)

    message_title = Label.new()
    message_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    message_title.add_theme_font_size_override("font_size", 56)
    message_box.add_child(message_title)

    message_subtitle = Label.new()
    message_subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    message_subtitle.add_theme_font_size_override("font_size", 24)
    message_box.add_child(message_subtitle)

    _show_message("No scene loaded", "Waiting for pinballctl commands")


func _process(_delta: float) -> void:
    if pending_video_path.is_empty():
        return
    if not FileAccess.file_exists(pending_video_path):
        return
    var path := pending_video_path
    var key := pending_video_key
    var loop_enabled := pending_video_loop
    pending_video_path = ""
    pending_video_key = ""
    pending_video_loop = false
    play_video(key, path, loop_enabled)


func preload_media(media_rows: Array) -> Dictionary:
    return {"ok": true, "preloaded": media_rows.size()}


func play_video(media_key: String, media_path: String, loop_enabled: bool) -> Dictionary:
    current_media_key = media_key
    current_media_path = media_path
    current_loop = loop_enabled
    var ext: String = media_path.get_extension().to_lower()
    _clear_media()
    if ext not in ["ogv", "ogg"]:
        current_status = "unsupported"
        _show_message(current_scene_name, "Video playback not yet supported for .%s assets" % ext)
        return {"ok": false, "error": "unsupported_video_format", "path": media_path, "ext": ext, "playback": status()}
    var stream := VideoStreamTheora.new()
    stream.file = media_path
    video_player.stream = stream
    if video_player.stream != null:
        video_player.loop = loop_enabled
        image_view.visible = false
        message_wrap.visible = false
        video_player.visible = true
        video_player.play()
        current_status = "playing"
        return {"ok": true, "playback": status()}
    current_status = "stopped"
    return {"ok": false, "error": "video_load_failed", "path": media_path}


func stop_video() -> Dictionary:
    _clear_media()
    current_status = "stopped"
    pending_video_path = ""
    pending_video_key = ""
    pending_video_loop = false
    video_player.stop()
    video_player.stream = null
    current_media_key = ""
    current_media_path = ""
    current_loop = false
    return {"ok": true, "playback": status()}


func pause_video() -> Dictionary:
    if video_player.stream == null:
        return {"ok": true, "playback": status()}
    video_player.paused = true
    current_status = "paused"
    return {"ok": true, "playback": status()}


func status() -> Dictionary:
    var playback_state := current_status
    if playback_state.is_empty():
        if video_player.is_playing() and not video_player.paused:
            playback_state = "playing"
        elif video_player.paused:
            playback_state = "paused"
        else:
            playback_state = "stopped"
    return {
        "status": playback_state,
        "mediaKey": current_media_key,
        "mediaPath": current_media_path,
        "loop": current_loop,
        "positionMs": int(video_player.stream_position * 1000.0),
    }


func apply_state(render_state: Dictionary) -> Dictionary:
    var scene_data: Dictionary = {}
    if render_state.get("scene", {}) is Dictionary:
        scene_data = render_state.get("scene", {})
    var layers: Array = []
    if render_state.get("layers", []) is Array:
        layers = render_state.get("layers", [])
    var playback: Dictionary = {}
    if render_state.get("playback", {}) is Dictionary:
        playback = render_state.get("playback", {})
    current_scene_key = str(scene_data.get("key", "no_scene"))
    current_scene_name = str(scene_data.get("name", "No scene loaded"))
    current_loop = bool(playback.get("loop", false))
    if layers.is_empty():
        current_media_key = ""
        current_media_path = ""
        current_status = "stopped"
        _clear_media()
        _show_message("No scene loaded", "Waiting for pinballctl commands")
        return {"ok": true, "playback": status()}
    var top_layer: Dictionary = {}
    if layers[layers.size() - 1] is Dictionary:
        top_layer = layers[layers.size() - 1]
    var asset: Dictionary = {}
    if top_layer.get("asset", {}) is Dictionary:
        asset = top_layer.get("asset", {})
    var asset_kind: String = str(asset.get("kind", "")).to_lower()
    var asset_path: String = str(asset.get("path", ""))
    current_media_key = str(asset.get("id", top_layer.get("layerId", "")))
    current_media_path = asset_path
    if asset_kind == "image":
        return _apply_image(asset_path, current_scene_name)
    if asset_kind == "video":
        pending_video_path = ""
        pending_video_key = ""
        pending_video_loop = false
        return play_video(current_media_key, asset_path, current_loop)
    if asset_kind == "pending_video":
        pending_video_path = asset_path
        pending_video_key = current_media_key
        pending_video_loop = current_loop
        _clear_media()
        current_status = "preparing"
        _show_message(current_scene_name, "Preparing video...")
        return {"ok": true, "playback": status()}
    _clear_media()
    current_status = "stopped"
    if current_scene_key == "no_scene":
        _show_message("No scene loaded", "Waiting for pinballctl commands")
    else:
        _show_message(current_scene_name, "No base asset configured")
    return {"ok": true, "playback": status()}


func _apply_image(asset_path: String, scene_title: String) -> Dictionary:
    _clear_media()
    var image := Image.new()
    var err: Error = image.load(asset_path)
    if err != OK:
        current_status = "stopped"
        _show_message(scene_title, "Image failed to load")
        return {"ok": false, "error": "image_load_failed", "path": asset_path, "playback": status()}
    var texture := ImageTexture.create_from_image(image)
    image_view.texture = texture
    image_view.visible = true
    message_wrap.visible = false
    current_status = "displaying"
    return {"ok": true, "playback": status()}


func _show_message(title: String, subtitle: String) -> void:
    _clear_media()
    message_title.text = title
    message_subtitle.text = subtitle
    message_wrap.visible = true


func _clear_media() -> void:
    video_player.stop()
    video_player.stream = null
    video_player.visible = false
    image_view.texture = null
    image_view.visible = false
    message_wrap.visible = false
