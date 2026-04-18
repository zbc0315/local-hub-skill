import pytest

from hub.paths import RootPath


class TestRootPath:
    def test_local_absolute(self) -> None:
        rp = RootPath.parse("/srv/data-hub")
        assert not rp.is_remote
        assert rp.local_path == "/srv/data-hub"
        assert rp.user is None
        assert rp.host is None

    def test_remote(self) -> None:
        rp = RootPath.parse("jim@nas.lan:/srv/data-hub")
        assert rp.is_remote
        assert rp.user == "jim"
        assert rp.host == "nas.lan"
        assert rp.remote_path == "/srv/data-hub"

    def test_relative_paths_rejected(self) -> None:
        with pytest.raises(ValueError):
            RootPath.parse("relative/path")

    def test_malformed_remote_rejected(self) -> None:
        # missing path part
        with pytest.raises(ValueError):
            RootPath.parse("jim@nas.lan:")
        # missing user
        with pytest.raises(ValueError):
            RootPath.parse("@nas.lan:/path")

    def test_dataset_path_local(self) -> None:
        rp = RootPath.parse("/srv/data-hub")
        assert rp.dataset_path("covid-jhu") == "/srv/data-hub/datasets/covid-jhu"

    def test_dataset_path_remote(self) -> None:
        rp = RootPath.parse("jim@nas.lan:/srv/data-hub")
        # Remote renders as user@host:path for rsync/scp
        assert rp.dataset_path("covid-jhu") == "jim@nas.lan:/srv/data-hub/datasets/covid-jhu"
        assert rp.server_dataset_path("covid-jhu") == "/srv/data-hub/datasets/covid-jhu"
