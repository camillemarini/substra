# Copyright 2018 Owkin, inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import re
import tempfile
from unittest import mock

import click
from click.testing import CliRunner
import pytest

import substra
from substra.cli.interface import cli, click_option_output_format, error_printer

from . import datastore


@pytest.fixture
def workdir(tmp_path):
    d = tmp_path / "substra-cli"
    d.mkdir()
    return d


def execute(command, exit_code=0):
    runner = CliRunner()
    result = runner.invoke(cli, command)
    assert result.exit_code == exit_code
    return result.output


def client_execute(tmpdir, command, exit_code=0):
    # force using a new config file and a new profile
    if '--config' not in command:
        cfgpath = tmpdir / 'substra.cfg'
        substra.sdk.config.Manager(str(cfgpath)).add_profile(
            'default', url='http://foo')
        command.extend(['--config', str(cfgpath)])
    return execute(command, exit_code=exit_code)


def test_command_help():
    output = execute(['--help'])
    assert 'Usage:' in output


def test_command_version():
    output = execute(['--version'])
    assert substra.__version__ in output


def test_command_config(workdir):
    cfgfile = workdir / "cli.cfg"

    assert cfgfile.exists() is False

    new_url = 'http://foo'
    new_profile = 'foo'
    execute([
        'config',
        new_url,
        '--profile', new_profile,
        '--config', str(cfgfile),
    ])
    assert cfgfile.exists()

    # check new profile has been created, check also that default profile
    # has been created
    with cfgfile.open() as fp:
        cfg = json.load(fp)
    expected_profiles = ['default', 'foo']
    assert list(cfg.keys()) == expected_profiles


def mock_client_call(mocker, method_name, response="", side_effect=None):
    return mocker.patch(f'substra.cli.interface.Client.{method_name}',
                        return_value=response, side_effect=side_effect)


@pytest.mark.parametrize(
    'asset_name', ['objective', 'dataset', 'algo', 'testtuple', 'traintuple']
)
def test_command_list(asset_name, workdir, mocker):
    item = getattr(datastore, asset_name.upper())
    method_name = f'list_{asset_name}'
    with mock_client_call(mocker, method_name, [item]) as m:
        output = client_execute(workdir, ['list', asset_name])
    assert m.is_called()
    assert item['key'] in output


def test_command_list_node(workdir, mocker):
    with mock_client_call(mocker, 'list_node', datastore.NODES):
        output = client_execute(workdir, ['list', 'node'])
    assert output == ('NODE ID                     \n'
                      'foo                         \n'
                      'bar         (current)       \n')


@pytest.mark.parametrize('asset_name,params', [
    ('dataset', []),
    ('algo', []),
    ('traintuple', ['--objective-key', 'foo', '--algo-key', 'foo', '--dataset-key', 'foo',
                    '--data-samples-path']),
    ('testtuple', ['--traintuple-key', 'foo', '--data-samples-path'])]
)
def test_command_add(asset_name, params, workdir, mocker):
    method_name = f'add_{asset_name}'

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as file,\
            mock_client_call(mocker, method_name, response={}) as m:
        json.dump({}, file)
        file.seek(0)

        client_execute(workdir, ['add', asset_name] + params + [file.name])
    assert m.is_called()

    with tempfile.NamedTemporaryFile(suffix='.md') as file:
        res = client_execute(workdir, ['add', asset_name] + params + [file.name], exit_code=2)
        assert re.search(r'File ".*" is not a valid JSON file\.', res)

    res = client_execute(workdir, ['add', asset_name] + params + ['non_existing_file.txt'],
                         exit_code=2)
    assert re.search(r'File ".*" does not exist\.', res)


def test_command_add_objective(workdir, mocker):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as file:
        json.dump({}, file)
        file.seek(0)

        with mock_client_call(mocker, 'add_objective', response={}) as m:
            client_execute(workdir, ['add', 'objective', file.name, '--dataset-key', 'foo',
                                     '--data-samples-path', file.name])
        assert m.is_called()

        with mock_client_call(mocker, 'add_objective', response={}) as m:
            client_execute(workdir, ['add', 'objective', file.name])
        assert m.is_called()

        res = client_execute(workdir, ['add', 'objective', 'non_existing_file.txt', '--dataset-key',
                                       'foo', '--data-samples-path', file.name], exit_code=2)
        assert re.search(r'File ".*" does not exist\.', res)

        res = client_execute(workdir, ['add', 'objective', file.name, '--dataset-key', 'foo',
                                       '--data-samples-path', 'non_existing_file.txt'], exit_code=2)
        assert re.search(r'File ".*" does not exist\.', res)

        with tempfile.NamedTemporaryFile(suffix='.md') as md_file:
            res = client_execute(workdir, ['add', 'objective', md_file.name, '--dataset-key', 'foo',
                                           '--data-samples-path', file.name], exit_code=2)
            assert re.search(r'File ".*" is not a valid JSON file\.', res)

            res = client_execute(workdir, ['add', 'objective', file.name, '--dataset-key', 'foo',
                                           '--data-samples-path', md_file.name], exit_code=2)
            assert re.search(r'File ".*" is not a valid JSON file\.', res)


def test_command_add_testtuple_no_data_samples(mocker, workdir):
    with mock_client_call(mocker, 'add_testtuple', response={}) as m:
        client_execute(workdir, ['add', 'testtuple', '--traintuple-key', 'foo'])
    assert m.is_called()


def test_command_add_data_sample(workdir, mocker):
    temp_dir = tempfile.mkdtemp()

    with mock_client_call(mocker, 'add_data_samples') as m:
        client_execute(workdir, ['add', 'data_sample', temp_dir, '--dataset-key', 'foo',
                                 '--test-only'])
    assert m.is_called()

    res = client_execute(workdir, ['add', 'data_sample', 'dir', '--dataset-key', 'foo'],
                         exit_code=2)
    assert re.search(r'Directory ".*" does not exist\.', res)


def test_command_add_already_exists(workdir, mocker):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as file, \
            mock_client_call(mocker, 'add_dataset',
                             side_effect=substra.exceptions.AlreadyExists('foo', 409)) as m:
        json.dump({}, file)
        file.seek(0)
        output = client_execute(workdir, ['add', 'dataset', file.name], exit_code=1)

        assert 'already exists' in output
        assert m.is_called()


@pytest.mark.parametrize(
    'asset_name', ['objective', 'dataset', 'algo', 'testtuple', 'traintuple']
)
def test_command_get(asset_name, workdir, mocker):
    item = getattr(datastore, asset_name.upper())
    method_name = f'get_{asset_name}'
    with mock_client_call(mocker, method_name, item) as m:
        output = client_execute(workdir, ['get', asset_name, 'fakekey'])
    assert m.is_called()
    assert item['key'] in output


def test_command_describe(workdir, mocker):
    response = "My description."
    with mock_client_call(mocker, 'describe_objective', response) as m:
        output = client_execute(workdir, ['describe', 'objective', 'fakekey'])
    assert m.is_called()
    assert response in output


def test_command_download(workdir, mocker):
    with mock_client_call(mocker, 'download_objective') as m:
        client_execute(workdir, ['download', 'objective', 'fakekey'])
    assert m.is_called()


def test_command_update_dataset(workdir, mocker):
    with mock_client_call(mocker, 'update_dataset') as m:
        client_execute(workdir, ['update', 'dataset', 'key1', 'key2'])
    assert m.is_called()


def test_command_update_data_sample(workdir, mocker):
    data_samples = {
        'keys': ['key1', 'key2'],
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as file,\
            mock_client_call(mocker, 'link_dataset_with_data_samples') as m:
        json.dump(data_samples, file)
        file.seek(0)

        client_execute(workdir, ['update', 'data_sample', file.name,
                                 '--dataset-key', 'foo'])
    assert m.is_called()

    with tempfile.NamedTemporaryFile(suffix='.json') as file:
        file.write(b'test')
        res = client_execute(workdir, ['update', 'data_sample', file.name,
                                       '--dataset-key', 'foo'], exit_code=2)
        assert re.search(r'File ".*" is not a valid JSON file\.', res)

    res = client_execute(workdir, ['update', 'data_sample', 'non_existing_file.txt',
                                   '--dataset-key', 'foo'], exit_code=2)
    assert re.search(r'File ".*" does not exist\.', res)


@pytest.mark.parametrize('params,output', [
    ([], 'pretty\n'),
    (['--pretty'], 'pretty\n'),
    (['--json'], 'json\n'),
    (['--yaml'], 'yaml\n'),
])
def test_option_output_format(params, output):
    @click.command()
    @click_option_output_format
    def foo(output_format):
        click.echo(output_format)

    runner = CliRunner()

    res = runner.invoke(foo, params)
    assert res.output == output


@pytest.mark.parametrize('exception', [
    (substra.exceptions.RequestException("foo", 400)),
    (substra.exceptions.ConnectionError("foo", 400)),
    (substra.exceptions.InvalidResponse(None, 'foo')),
    (substra.exceptions.LoadDataException("foo", 400)),
])
def test_error_printer(mocker, exception):
    @error_printer
    def foo():
        raise exception

    mock_click_context = mock.MagicMock()
    mock_click_context.params = {'verbose': False}

    with mocker.patch('substra.cli.interface.click.get_current_context',
                      return_value=mock_click_context):
        with pytest.raises(click.ClickException, match='foo'):
            foo()
