import hashlib
import os
import shutil
import time
import uuid

import pytest
from quetz.pkgstores import AzureBlobStore, LocalStore, S3Store, has_xattr

s3_config = {
    'key': os.environ.get("S3_ACCESS_KEY"),
    'secret': os.environ.get("S3_SECRET_KEY"),
    'url': os.environ.get("S3_ENDPOINT"),
    'region': os.environ.get("S3_REGION"),
    'bucket_prefix': "test",
    'bucket_suffix': "",
}

azure_config = {
    'account_name': os.environ.get("AZURE_ACCOUNT_NAME"),
    'account_access_key': os.environ.get("AZURE_ACCESS_KEY"),
    'conn_str': os.environ.get("AZURE_CONN_STRING"),
    'container_prefix': "test",
    'container_suffix': "",
}

test_dir = os.path.dirname(__file__)


def test_local_store():

    temp_dir = os.path.join(test_dir, "test_pkg_store_" + str(int(time.time())))
    os.makedirs(temp_dir, exist_ok=False)

    pkg_store = LocalStore({'channels_dir': temp_dir})

    pkg_store.add_file("content", "my-channel", "test.txt")
    pkg_store.add_file("content".encode('ascii'), "my-channel", "test_2.txt")

    files = pkg_store.list_files("my-channel")

    assert files == ["test.txt", "test_2.txt"]

    pkg_store.delete_file("my-channel", "test.txt")

    files = pkg_store.list_files("my-channel")
    assert files == ["test_2.txt"]

    with pkg_store.serve_path("my-channel", "test_2.txt") as f:
        assert f.read().decode('utf-8') == "content"

    metadata = pkg_store.get_filemetadata("my-channel", "test_2.txt")

    assert metadata[0] > 0
    assert type(metadata[1]) is float

    if has_xattr:
        md5 = hashlib.md5("content".encode('ascii')).hexdigest()
        assert metadata[2] == md5
    else:
        assert type(metadata[2]) is str

    shutil.rmtree(temp_dir)


@pytest.fixture
def channel_name():
    return "mychannel" + str(uuid.uuid4())


@pytest.fixture
def local_store():
    temp_dir = os.path.join(test_dir, "test_pkg_store_" + str(int(time.time())))
    os.makedirs(temp_dir, exist_ok=False)

    pkg_store = LocalStore({'channels_dir': temp_dir})

    yield pkg_store

    shutil.rmtree(temp_dir)


@pytest.fixture(
    params=[
        "local_store",
        pytest.param(
            "s3_store",
            marks=pytest.mark.skipif(
                not s3_config['key'], reason="requires s3 credentials"
            ),
        ),
        pytest.param(
            "azure_store",
            marks=pytest.mark.skipif(
                not azure_config['account_access_key'],
                reason="requires azure credentials",
            ),
        ),
    ]
)
def any_store(request):
    val = request.getfixturevalue(request.param)
    return val


def test_remove_dirs(any_store, channel_name):
    any_store.create_channel(channel_name)
    any_store.add_file("content", channel_name, "test.txt")

    with any_store.serve_path(channel_name, "test.txt") as f:
        assert f.read().decode('utf-8') == "content"

    any_store.remove_channel(channel_name)

    with pytest.raises(FileNotFoundError):
        with any_store.serve_path(channel_name, "test.txt") as f:
            f.read()


@pytest.fixture
def s3_store():
    pkg_store = S3Store(s3_config)
    return pkg_store


@pytest.fixture
def azure_store():
    pkg_store = AzureBlobStore(azure_config)

    yield pkg_store


@pytest.fixture
def channel(any_store, channel_name):

    any_store.create_channel(channel_name)

    yield

    # cleanup
    any_store.remove_channel(channel_name)


def test_store_add_list_files(any_store, channel, channel_name):
    def assert_files(expected_files, n_retries=3):
        n_retries = 3

        for i in range(n_retries):
            try:
                files = pkg_store.list_files(channel_name)
                assert files == expected_files
            except AssertionError:
                continue
            break
        assert files == expected_files

    pkg_store = any_store

    pkg_store.add_file("content", channel_name, "test.txt")
    pkg_store.add_file("content", channel_name, "test_2.txt")

    assert_files(["test.txt", "test_2.txt"])

    pkg_store.delete_file(channel_name, "test.txt")

    assert_files(["test_2.txt"])

    metadata = pkg_store.get_filemetadata(channel_name, "test_2.txt")
    assert metadata[0] > 0
    assert type(metadata[1]) is float
    assert type(metadata[2]) is str


def test_move_file(any_store, channel, channel_name):
    def assert_files(expected_files, n_retries=3):
        n_retries = 3

        for i in range(n_retries):
            try:
                files = pkg_store.list_files(channel_name)
                assert files == expected_files
            except AssertionError:
                continue
            break
        assert files == expected_files

    pkg_store = any_store

    pkg_store.add_file("content", channel_name, "test.txt")
    pkg_store.move_file(channel_name, "test.txt", "test_2.txt")

    assert_files(['test_2.txt'])
