"""Unit tests for the `rdm-dmx` CLI entry point (rdm_dmx_async/cli.py)."""

import pytest

from rdm_dmx_async import cli


def test_list_ports_prints_each_port(capsys, monkeypatch):
    monkeypatch.setattr(cli, "list_available_ports", lambda: ["COM3", "COM4"])

    exit_code = cli._cmd_list_ports()

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "COM3" in out
    assert "COM4" in out


def test_list_ports_no_ports_found(capsys, monkeypatch):
    monkeypatch.setattr(cli, "list_available_ports", lambda: [])

    exit_code = cli._cmd_list_ports()

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "No serial ports found" in out


def test_parser_requires_a_command():
    parser = cli._build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_accepts_list_ports():
    parser = cli._build_parser()
    args = parser.parse_args(["list-ports"])
    assert args.command == "list-ports"


def test_parser_accepts_discover_with_options():
    parser = cli._build_parser()
    args = parser.parse_args(["discover", "--port", "COM5", "--timeout", "2.5"])
    assert args.command == "discover"
    assert args.port == "COM5"
    assert args.timeout == 2.5


async def test_async_main_dispatches_list_ports(monkeypatch):
    monkeypatch.setattr(cli, "list_available_ports", lambda: ["COM7"])

    exit_code = await cli._async_main(["list-ports"])

    assert exit_code == 0
