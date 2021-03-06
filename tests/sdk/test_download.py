import pytest
import os

import substra

from .. import datastore
from .utils import mock_requests, mock_requests_response


@pytest.mark.parametrize(
    'asset_name, filename', [
        ('dataset', 'opener.py'),
        ('algo', 'algo.tar.gz'),
        ('objective', 'metrics.py')
    ]
)
def test_download_asset(asset_name, filename, tmp_path, client, mocker):
    item = getattr(datastore, asset_name.upper())
    asset_response = mock_requests_response(item)

    description_response = mock_requests_response('foo')

    m = mocker.patch('substra.sdk.rest_client.requests.get',
                     side_effect=[asset_response, description_response])

    method = getattr(client, f'download_{asset_name}')
    method("foo", tmp_path)

    temp_file = str(tmp_path) + '/' + filename
    assert os.path.exists(temp_file)
    assert m.is_called()


@pytest.mark.parametrize(
    'asset_name', ['dataset', 'algo', 'objective']
)
def test_download_asset_not_found(asset_name, tmp_path, client, mocker):
    m = mock_requests(mocker, "get", status=404)

    with pytest.raises(substra.sdk.exceptions.NotFound):
        method = getattr(client, f'download_{asset_name}')
        method('foo', tmp_path)

    assert m.call_count == 1


@pytest.mark.parametrize(
    'asset_name', ['dataset', 'algo', 'objective']
)
def test_download_content_not_found(asset_name, tmp_path, client, mocker):
    item = getattr(datastore, asset_name.upper())
    asset_response = mock_requests_response(item)

    description_response = mock_requests_response('foo', status=404)

    m = mocker.patch('substra.sdk.rest_client.requests.get',
                     side_effect=[asset_response, description_response])

    method = getattr(client, f'download_{asset_name}')

    with pytest.raises(substra.sdk.exceptions.NotFound):
        method("key", tmp_path)

    assert m.call_count == 2
