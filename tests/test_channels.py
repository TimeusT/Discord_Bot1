from src.placebot.channels import ChannelStore


def test_nothing_is_watched_at_first(tmp_path):
    store = ChannelStore(tmp_path / "channels.json")
    assert not store.is_watched(1, 10)
    assert store.get(1) == frozenset()


def test_choices_are_remembered_per_server(tmp_path):
    store = ChannelStore(tmp_path / "channels.json")
    store.set(1, [10, 11])
    store.set(2, [20])
    assert store.is_watched(1, 10)
    assert not store.is_watched(1, 20)  # a channel from another server
    assert store.get(2) == frozenset({20})


def test_choices_survive_a_restart(tmp_path):
    path = tmp_path / "nested" / "channels.json"  # folder is created automatically
    ChannelStore(path).set(1, [10])
    assert ChannelStore(path).is_watched(1, 10)


def test_choosing_again_replaces_the_old_choice(tmp_path):
    store = ChannelStore(tmp_path / "channels.json")
    store.set(1, [10, 11])
    store.set(1, [])
    assert store.get(1) == frozenset()


def test_a_damaged_file_does_not_crash_the_bot(tmp_path):
    path = tmp_path / "channels.json"
    path.write_text("{not valid json", encoding="utf-8")
    assert ChannelStore(path).get(1) == frozenset()
