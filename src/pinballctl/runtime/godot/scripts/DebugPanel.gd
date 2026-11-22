extends PanelContainer

@onready var title_value: Label = $Margin/VBox/TitleValue
@onready var state_value: Label = $Margin/VBox/Grid/StateValue
@onready var health_value: Label = $Margin/VBox/Grid/HealthValue
@onready var scene_value: Label = $Margin/VBox/Grid/SceneValue
@onready var playback_value: Label = $Margin/VBox/Grid/PlaybackValue
@onready var display_value: Label = $Margin/VBox/Grid/DisplayValue
@onready var mode_value: Label = $Margin/VBox/Grid/ModeValue
@onready var stack_value: Label = $Margin/VBox/Grid/StackValue
@onready var target_value: Label = $Margin/VBox/Grid/TargetValue
@onready var overlays_value: Label = $Margin/VBox/Grid/OverlaysValue
@onready var command_value: Label = $Margin/VBox/CommandValue
var debug_enabled: bool = true


func set_debug_enabled(enabled: bool) -> void:
    debug_enabled = enabled
    visible = debug_enabled


func set_snapshot(snapshot: Dictionary) -> void:
    visible = debug_enabled
    if debug_enabled == false:
        return
    title_value.text = str(snapshot.get("title", "PinballCTL Godot Runtime"))
    state_value.text = str(snapshot.get("state", "unknown"))
    health_value.text = str(snapshot.get("health", "unknown"))
    scene_value.text = str(snapshot.get("scene", ""))
    playback_value.text = str(snapshot.get("playback", "stopped"))
    display_value.text = str(snapshot.get("display", ""))
    mode_value.text = str(snapshot.get("mode", "-"))
    stack_value.text = str(snapshot.get("stack", "-"))
    target_value.text = str(snapshot.get("target", "-"))
    overlays_value.text = str(snapshot.get("overlays", ""))
    command_value.text = str(snapshot.get("command", "Waiting for commands"))
