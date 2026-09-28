from engine.perspective.knowledge import PerspectiveStore
from engine.scene.state import SceneManager


def test_absent_pulpo_does_not_learn_hidden_object_location(database) -> None:
    scene = SceneManager(database)
    perspective = PerspectiveStore(database)
    scene.set_presence("pulpo", False)
    perspective.set_object_location("small key", "under the box", {"user"})
    scene.set_presence("pulpo", True)
    assert perspective.known_value("object_location:small key", "user") == "under the box"
    assert perspective.known_value("object_location:small key", "pulpo") is None

