from tools.security_scan import scan_agent_source


def test_security_scan_blocks_network_and_subprocess():
    source = """
import requests
import subprocess

def select_move(observation, output_format="uci", time_limit_ms=100):
    subprocess.run(["echo", "x"])
    return "e2e4"
"""
    report = scan_agent_source(source)
    assert not report.passed
    assert "forbidden import: requests" in report.issues
    assert "forbidden import: subprocess" in report.issues
    assert "forbidden method call: run" in report.issues


def test_security_scan_allows_local_chess_agent_shape():
    source = """
from typing import Any
import chess

def select_move(observation: Any, output_format: str = "uci", time_limit_ms: int = 100) -> str:
    board = chess.Board()
    return next(iter(board.legal_moves)).uci()
"""
    assert scan_agent_source(source).passed

